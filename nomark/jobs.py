from __future__ import annotations

import asyncio
import json
import multiprocessing
import os
from pathlib import Path
import signal
import sys
import tempfile
import time


def worker(directory: str, mode: str, name: str) -> None:
    os.setsid()
    root = Path(directory)
    # Parent cleanup also owns upstream/native staging after a forced kill.
    os.environ['TMPDIR'] = str(root)
    tempfile.tempdir = str(root)
    if sys.platform == "linux":
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024, 768 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_FSIZE, (256 * 1024 * 1024, 256 * 1024 * 1024))
    # A parser can emit user content in warnings; child diagnostics stay private.
    with open(os.devnull, "w") as sink:
        os.dup2(sink.fileno(), 1)
        os.dup2(sink.fileno(), 2)
    from nomark.engine import ProcessingError, process_file, process_text

    try:
        if mode == "text":
            result = process_text((root / "input").read_text(encoding="utf-8"))
        else:
            result = process_file(root / "input", name, root)
        payload = {"ok": True, **result}
    except ProcessingError as exc:
        payload = {"ok": False, "error": exc.code, "http_status": exc.status}
    except Exception:
        payload = {"ok": False, "error": "processing_failed", "http_status": 422}
    (root / "response.json").write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")


class JobError(Exception):
    def __init__(self, code: str, status: int):
        self.code, self.status = code, status


def kill_tree(process) -> None:
    if process.pid is None:
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        if process.is_alive():
            process.kill()
    process.join(timeout=2)
    if not process.is_alive():
        process.close()


class Jobs:
    def __init__(self, *, timeout: float = 60, concurrency: int = 2, temp_root: str | None = None):
        self.timeout = timeout
        self.concurrency = concurrency
        self.temp_root = temp_root
        self.active = 0

    async def run(self, mode: str, content: bytes, name: str = "") -> dict:
        if self.active >= self.concurrency:
            raise JobError("server_busy", 503)
        self.active += 1
        try:
            with tempfile.TemporaryDirectory(prefix="nomark-", dir=self.temp_root) as directory:
                root = Path(directory)
                (root / "input").write_bytes(content)
                process = multiprocessing.get_context("spawn").Process(target=worker, args=(directory, mode, name))
                started = time.monotonic()
                try:
                    process.start()
                    while process.is_alive():
                        if time.monotonic() - started >= self.timeout:
                            raise JobError("processing_timeout", 504)
                        await asyncio.sleep(0.05)
                    response = root / "response.json"
                    if process.exitcode != 0 or not response.exists():
                        raise JobError("processing_failed", 422)
                    payload = json.loads(response.read_text(encoding="utf-8"))
                    if not payload.get("ok"):
                        raise JobError(payload["error"], payload["http_status"])
                    payload["elapsed_ms"] = round((time.monotonic() - started) * 1000)
                    return payload
                finally:
                    kill_tree(process)
        finally:
            self.active -= 1
