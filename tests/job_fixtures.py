import os
from pathlib import Path
import subprocess
import time


def slow_worker(directory, mode, name):
    os.setsid()
    child = subprocess.Popen(["/bin/sh", "-c", "sleep 30"])
    Path(name).write_text(str(child.pid))
    time.sleep(30)
