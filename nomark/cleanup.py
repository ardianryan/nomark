"""Remove expired job directories relative to a trusted directory descriptor."""
import os
from pathlib import Path
import shutil
import stat
import time


def cleanup_stale_jobs(workdir: Path, max_age: float = 300):
    # Fail closed on platforms without Python's descriptor-based safe rmtree.
    if not shutil.rmtree.avoids_symlink_attacks:
        return
    descriptor = None
    try:
        descriptor = os.open(workdir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        with os.scandir(descriptor) as entries:
            names = [entry.name for entry in entries if entry.name.startswith('nomark-')]
        for name in names:
            try:
                info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                if not stat.S_ISDIR(info.st_mode) or time.time() - info.st_mtime <= max_age:
                    continue
                shutil.rmtree(name, dir_fd=descriptor)
            except OSError:
                continue
    except OSError:
        return
    finally:
        if descriptor is not None:
            os.close(descriptor)
