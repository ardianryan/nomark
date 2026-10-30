"""One warm inference process with a hard wall deadline and cancellation."""
import asyncio
import json
import hashlib
import multiprocessing
import os
from pathlib import Path
import signal
import time


def infer(connection, model_root):
    os.setsid()
    with open(os.devnull, 'w') as sink:
        os.dup2(sink.fileno(), 1)
        os.dup2(sink.fileno(), 2)
    from .pipeline import Pipeline
    try:
        pipeline = Pipeline(model_root)
        connection.send_bytes(b'{"ready":true}')
        while True:
            request = json.loads(connection.recv_bytes(65536))
            result = pipeline.paraphrase(request['text'], request['language'])
            connection.send_bytes(json.dumps(result, ensure_ascii=True).encode())
            del request, result
    except Exception:
        try:
            connection.send_bytes(b'{"ok":false}')
        except (BrokenPipeError, OSError):
            pass
    finally:
        connection.close()


class Runtime:
    def __init__(self, directory, timeout=75, idle=300, target=infer):
        self.directory, self.timeout, self.idle, self.target = directory, timeout, idle, target
        self.process = self.connection = None
        self.lock = asyncio.Lock()
        self.last_used = 0
        self.verified = False

    def ready(self):
        if self.verified:
            return True
        try:
            root = Path(self.directory)
            checksums = json.loads((root / 'checksums.json').read_text())
            required = {f'{pair}/{name}' for pair in ('en-id', 'id-en')
                        for name in ('model.bin', 'tokenizer/tokenizer_config.json', 'tokenizer/source.spm', 'tokenizer/target.spm', 'tokenizer/vocab.json')}
            if not required.issubset(checksums):
                return False
            for name, expected in checksums.items():
                relative = Path(name)
                if relative.is_absolute() or '..' in relative.parts:
                    return False
                with (root / relative).open('rb') as stream:
                    if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                        return False
            self.verified = True
            return True
        except (OSError, ValueError, TypeError):
            return False

    def stop(self):
        if self.process:
            if self.process.is_alive():
                try:
                    os.killpg(self.process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    self.process.kill()
            self.process.join(timeout=2)
            if self.process.is_alive():
                raise RuntimeError('worker_did_not_stop')
            self.process.close()
        if self.connection:
            self.connection.close()
        self.process = self.connection = None

    async def process_text(self, text, language, disconnected):
        if self.lock.locked():
            raise RuntimeError('busy')
        async with self.lock:
            try:
                started = time.monotonic()
                if not self.process or not self.process.is_alive():
                    self.stop()
                    ctx = multiprocessing.get_context('spawn')
                    self.connection, child = ctx.Pipe()
                    self.process = ctx.Process(target=self.target, args=(child, self.directory))
                    self.process.start()
                    child.close()
                    while not self.connection.poll():
                        if time.monotonic() - started >= self.timeout:
                            raise TimeoutError
                        if await disconnected():
                            raise asyncio.CancelledError
                        if not self.process.is_alive():
                            raise RuntimeError('worker_failed')
                        await asyncio.sleep(0.025)
                    if json.loads(self.connection.recv_bytes(1024)).get('ready') is not True:
                        raise RuntimeError('worker_failed')
                await asyncio.to_thread(self.connection.send_bytes, json.dumps({'text': text, 'language': language}).encode())
                while not self.connection.poll():
                    if time.monotonic() - started >= self.timeout:
                        raise TimeoutError
                    if await disconnected():
                        raise asyncio.CancelledError
                    if not self.process.is_alive():
                        raise RuntimeError('worker_failed')
                    await asyncio.sleep(0.025)
                result = json.loads(self.connection.recv_bytes(1024 * 1024))
                if result.get('ok') is not True:
                    raise RuntimeError('worker_failed')
                return result
            except BaseException:
                self.stop()
                raise
            finally:
                self.last_used = time.monotonic()

    def sweep(self):
        if not self.lock.locked() and self.process and time.monotonic() - self.last_used >= self.idle:
            self.stop()
