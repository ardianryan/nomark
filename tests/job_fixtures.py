import os
from pathlib import Path
import subprocess
import time


def slow_worker(directory, mode, name):
    os.setsid()
    child = subprocess.Popen(["/bin/sh", "-c", "sleep 30"])
    Path(name).write_text(str(child.pid))
    time.sleep(30)


def resource_probe_worker(directory, mode, name):
    import errno
    import resource
    from nomark import engine
    from nomark.jobs import worker

    def probe(text):
        try:
            bytearray(800 * 1024 * 1024)
        except MemoryError:
            memory_blocked = True
        else:
            memory_blocked = False
        file_blocked = False
        try:
            with (Path(directory) / 'oversized').open('wb') as stream:
                stream.truncate(257 * 1024 * 1024)
        except OSError as exc:
            file_blocked = exc.errno == errno.EFBIG
        return {
            'memory_blocked': memory_blocked,
            'file_blocked': file_blocked,
            'address_space': resource.getrlimit(resource.RLIMIT_AS),
            'file_size': resource.getrlimit(resource.RLIMIT_FSIZE),
        }

    engine.process_text = probe
    worker(directory, mode, name)


def paused_attachment_worker(directory, mode, name):
    import json
    from nomark import upstream
    from nomark.jobs import worker

    extract = upstream.container_meta._pdf_show_attachment

    def pause_after_extraction(path, key, destination, deadline):
        count = extract(path, key, destination, deadline)
        marker = Path(directory).parent.parent / 'attachment-started.json'
        marker.write_text(json.dumps({'path': str(destination), 'bytes': count}))
        time.sleep(30)
        return count

    upstream.container_meta._pdf_show_attachment = pause_after_extraction
    worker(directory, mode, name)
