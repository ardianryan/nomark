"""One isolated process per image; capacity stays blocked until termination."""
import asyncio
import base64
from contextlib import contextmanager
import json
import multiprocessing
import os
from pathlib import Path
import signal
import shutil
import stat
import tempfile
import time

from .pipeline import ImageError, MAX_INPUT, MAX_OUTPUT


def worker(directory, name):
    os.setsid()
    root = Path(directory)
    os.environ['TMPDIR'] = str(root)
    tempfile.tempdir = str(root)
    if os.name == 'posix':
        import resource
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OUTPUT, MAX_OUTPUT))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    with open(os.devnull, 'w') as sink:
        os.dup2(sink.fileno(), 1)
        os.dup2(sink.fileno(), 2)
    try:
        from .sandbox import deny_network
        deny_network()
        from .pipeline import process
        report = process(root / ('input' + Path(name).suffix.lower()), name, root / 'output.png')
        result = {'ok': True, **report}
    except ImageError as exc:
        result = {'ok': False, 'error': exc.code, 'http_status': exc.status}
    except Exception:
        result = {'ok': False, 'error': 'processing_failed', 'http_status': 422}
    (root / 'report.json').write_text(json.dumps(result), encoding='utf-8')


class Runtime:
    def __init__(self, directory=None, timeout=60, target=worker):
        self.directory = directory or "/tmp/nomark-media"
        Path(self.directory).mkdir(parents=True, exist_ok=True, mode=0o700)
        self.timeout = timeout
        self.target = target
        self.lock = asyncio.Lock()
        self.process = None
        self.job_id = None
        self.cancelled = {}
        self.reject_until = 0
        self.blocked = False
        self.sweep()

    def sweep(self):
        now = time.monotonic()
        self.cancelled = {k: v for k, v in self.cancelled.items() if v > now}
        if self.job_id is not None or self.blocked or not shutil.rmtree.avoids_symlink_attacks:
            return
        descriptor = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            with os.scandir(descriptor) as entries:
                names = [e.name for e in entries if e.name.startswith('nomark-image-')]
            for name in names:
                try:
                    info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                    if stat.S_ISDIR(info.st_mode) and time.time() - info.st_mtime > 300:
                        shutil.rmtree(name, dir_fd=descriptor)
                except OSError:
                    continue
        finally:
            os.close(descriptor)

    def stop(self):
        if self.process is not None:
            if self.process.is_alive():
                try:
                    os.killpg(self.process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    self.process.kill()
            self.process.join(timeout=2)
            if self.process.is_alive():
                self.blocked = True
                raise RuntimeError('worker_did_not_stop')
            self.process.close()
            self.process = None
        self.blocked = False

    def cancel(self, job_id):
        self.sweep()
        if job_id not in self.cancelled and len(self.cancelled) >= 128:
            self.reject_until = time.monotonic() + 180
            raise RuntimeError('busy')
        # Tombstone a request cancelled before its POST arrives as well.
        self.cancelled[job_id] = time.monotonic() + 180
        if self.job_id == job_id:
            self.stop()
        return self.job_id != job_id or self.process is None

    @contextmanager
    def job_directory(self):
        directory = tempfile.mkdtemp(prefix='nomark-image-', dir=self.directory)
        try:
            yield directory
        finally:
            if not self.blocked:
                shutil.rmtree(directory)

    async def process_image(self, data, name, job_id, disconnected):
        from .pipeline import validate_name
        validate_name(name)
        if len(data) > MAX_INPUT:
            raise ImageError('file_too_large', 413)
        self.sweep()
        if self.lock.locked() or self.blocked or time.monotonic() < self.reject_until:
            raise ImageError('media_unavailable', 503)
        if job_id in self.cancelled:
            raise ImageError('request_cancelled', 499)
        async with self.lock:
            self.job_id = job_id
            try:
                with self.job_directory() as directory:
                    root = Path(directory)
                    (root / ('input' + Path(name).suffix.lower())).write_bytes(data)
                    ctx = multiprocessing.get_context('spawn')
                    started = time.monotonic()
                    self.process = ctx.Process(target=self.target, args=(directory, name))
                    self.process.start()
                    try:
                        while self.process is not None and self.process.is_alive():
                            if job_id in self.cancelled or await disconnected():
                                raise ImageError('request_cancelled', 499)
                            if time.monotonic() - started >= self.timeout:
                                raise ImageError('media_timeout', 504)
                            await asyncio.sleep(.025)
                        if job_id in self.cancelled:
                            raise ImageError('request_cancelled', 499)
                        path = root / 'report.json'
                        if not path.is_file() or path.stat().st_size > 16 * 1024 or self.process.exitcode != 0:
                            raise ImageError('processing_failed')
                        result = json.loads(path.read_bytes())
                        if result.get('ok') is not True:
                            raise ImageError(result.get('error', 'processing_failed'), result.get('http_status', 422))
                        output = root / 'output.png'
                        if not output.is_file() or output.stat().st_size > MAX_OUTPUT:
                            raise ImageError('output_too_large', 413)
                        encoded = base64.b64encode(output.read_bytes()).decode('ascii')
                        return {**result, 'cleaned_base64': encoded, 'bytes_in': len(data),
                                'bytes_out': output.stat().st_size, 'elapsed_ms': round((time.monotonic() - started) * 1000)}
                    finally:
                        self.stop()
            finally:
                self.job_id = None
