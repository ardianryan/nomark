"""Real-model smoke check against an isolated local NMT service."""
import json
import sys
import time
import urllib.request

base = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8001'
for _ in range(30):
    try:
        with urllib.request.urlopen(base + '/health', timeout=3) as response:
            assert json.load(response)['ready']
        break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit('NMT readiness failed')
for language, text in [('id', 'Saya tidak menyetujui perubahan jadwal tersebut.'),
                       ('en', 'Please keep the original meaning of this sentence.')]:
    request = urllib.request.Request(base + '/paraphrase', data=json.dumps({'text': text, 'language': language}).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=85) as response:
        result = json.load(response)
    assert result['ok'] and result['language'] == language and result['paraphrased_text']
    assert result['status'] in ('paraphrased', 'unchanged', 'partial')
    print(language, result['status'])
