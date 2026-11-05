"""Check actual app-to-media admission and image output using a synthetic fixture."""
import base64
import json
import os
from pathlib import Path
import time
import urllib.request

base=os.environ.get('NOMARK_SMOKE_URL','http://127.0.0.1:8000')
root=Path(__file__).resolve().parents[1]
for attempt in range(30):
    try:
        assert json.load(urllib.request.urlopen(base+'/api/media/capabilities',timeout=4))['available'];break
    except Exception:
        if attempt==29:raise
        time.sleep(.5)
ticket=json.load(urllib.request.urlopen(urllib.request.Request(base+'/api/media/queue',data=b'',method='POST')))['token']
source=(root/'tests/fixtures/images/supported-gemini.png').read_bytes()
boundary='nomark-staging-smoke'
body=(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="gemini.png"\r\nContent-Type: image/png\r\n\r\n'.encode()+source+f'\r\n--{boundary}--\r\n'.encode())
req=urllib.request.Request(base+'/api/image/process',data=body,headers={'Content-Type':'multipart/form-data; boundary='+boundary,'X-NoMark-Reservation':ticket})
with urllib.request.urlopen(req,timeout=90) as response:
    result=json.load(response)
    assert result['visual_status']=='cleaned' and result['kind']=='image' and result['report']['marks'][0]['key']=='gemini'
    decoded=base64.b64decode(result.pop('cleaned_base64'),validate=True)
    assert decoded[:8]==b'\x89PNG\r\n\x1a\n' and len(decoded)==result['bytes_out']
    assert response.headers['Cache-Control']=='no-store'
    print(json.dumps(result))
