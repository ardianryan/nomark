"""Collect synthetic sample outputs; this script never marks them reviewed."""
import json
import hashlib
from pathlib import Path
import sys
import time
import urllib.request

root = Path(__file__).resolve().parents[1]
source = Path(sys.argv[2]) if len(sys.argv) > 2 else root / 'docs/nmt-evaluation.json'
data = json.loads(source.read_text())
files = ['nmt-service/build_models.py', 'nmt-service/build.lock', 'nmt-service/requirements.lock', 'nmt-service/nmt_service/pipeline.py']
data['engine_fingerprint'] = hashlib.sha256(b''.join((root / name).read_bytes() for name in files)).hexdigest()
data.pop('summary', None)
base = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8001'
for row in data['samples']:
    started = time.monotonic()
    request = urllib.request.Request(base + '/paraphrase', data=json.dumps({'text': row['input'], 'language': row['language']}).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=85) as response:
        result = json.load(response)
    row.update(output=result['paraphrased_text'], status=result['status'],
               edits=result.get('edits', []),
               elapsed_ms=round((time.monotonic() - started) * 1000),
               reviewed=False, critical_error=None, language_acceptable=None)
    row.pop('notes', None)
print(json.dumps(data, ensure_ascii=False, indent=2))
