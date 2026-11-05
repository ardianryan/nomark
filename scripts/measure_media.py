"""Measure real per-process CPU image work with wait4 peak RSS on Linux."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from PIL import Image


def main():
    rows=[]
    with tempfile.TemporaryDirectory(prefix='nomark-measure-') as directory:
        root=Path(directory)
        for w,h in [(1000,1000),(2000,2000),(3200,2500)]:
            for fmt in ('PNG','JPEG','WEBP'):
                suffix={'PNG':'png','JPEG':'jpg','WEBP':'webp'}[fmt]
                source=root/f'input.{suffix}'
                # A repeated detailed source stresses detection and PNG encoding beyond a flat field.
                from PIL import ImageOps
                texture=Image.open('/fixtures/supported-gemini.png').convert('RGB').resize((w,h))
                texture.save(source,format=fmt)
                target=root/'output.png'
                code='from media_service.sandbox import deny_network; deny_network(); from pathlib import Path; from media_service.pipeline import process; import sys; process(Path(sys.argv[1]),sys.argv[2],Path(sys.argv[3]))'
                started=time.monotonic()
                p=subprocess.Popen([sys.executable,'-c',code,str(source),source.name,str(target)],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                while True:
                    pid,status,usage=os.wait4(p.pid,os.WNOHANG)
                    if pid: break
                    if time.monotonic()-started>60:
                        import signal
                        os.killpg(p.pid,signal.SIGKILL);pid,status,usage=os.wait4(p.pid,0);break
                    time.sleep(.025)
                p.returncode=os.waitstatus_to_exitcode(status)
                rows.append({'pixels':w*h,'format':fmt,'elapsed_ms':round((time.monotonic()-started)*1000),
                             'peak_rss_kib':usage.ru_maxrss,'exit_code':p.returncode,'bytes_in':source.stat().st_size,
                             'bytes_out':target.stat().st_size if target.exists() else 0})
                print(json.dumps(rows[-1]),flush=True)
                source.unlink();target.unlink(missing_ok=True)
    print(json.dumps({'version':'0.1.0-alpha.8','measurements':rows}),flush=True)
    if any(r['exit_code'] or r['elapsed_ms']>=60000 or r['peak_rss_kib']>=2*1024*1024 for r in rows): raise SystemExit(1)

if __name__=='__main__':main()
