"""Exercise the installed upstream image adapter through the private HTTP API."""
import io
import json
import time
import urllib.request
from PIL import Image

base='http://127.0.0.1:8002'
for attempt in range(30):
    try:
        with urllib.request.urlopen(base+'/health',timeout=3) as r:
            assert json.load(r)['ready']; break
    except Exception:
        if attempt==29: raise
        time.sleep(.5)
image=io.BytesIO();Image.new('RGBA',(96,80),(10,20,30,170)).save(image,'PNG')
boundary='nomark-smoke-boundary'
body=(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="smoke.png"\r\nContent-Type: image/png\r\n\r\n'.encode()+image.getvalue()+f'\r\n--{boundary}--\r\n'.encode())
request=urllib.request.Request(base+'/process',data=body,headers={'Content-Type':'multipart/form-data; boundary='+boundary,'X-NoMark-Job':'1'*32})
with urllib.request.urlopen(request,timeout=75) as r:
    result=json.load(r)
    assert result['ok'] and result['visual_status']=='no_watermark' and result['normalized'] is True
    assert r.headers['Cache-Control']=='no-store'
print('Media service smoke passed')
