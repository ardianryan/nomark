"""Fetch checksum-pinned model snapshots, convert offline, and hash runtime files."""
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request

from ctranslate2.converters import TransformersConverter

root = Path('/models')
root.mkdir(exist_ok=True)
manifest = json.loads(Path('models.lock.json').read_text())
for pair, model in manifest.items():
    snapshot = Path('/tmp') / pair
    snapshot.mkdir(exist_ok=True)
    for name, expected in model['files'].items():
        url = f"https://huggingface.co/{model['repository']}/resolve/{model['revision']}/{name}"
        target = snapshot / name
        digest = hashlib.sha256()
        with urllib.request.urlopen(url, timeout=300) as response, target.open('wb') as out:
            while chunk := response.read(1024 * 1024):
                digest.update(chunk)
                out.write(chunk)
        if digest.hexdigest() != expected:
            raise RuntimeError(f'Checksum mismatch: {pair}/{name}')
    destination = root / pair
    TransformersConverter(str(snapshot)).convert(str(destination), quantization='int8')
    tokenizer = destination / 'tokenizer'
    tokenizer.mkdir()
    for name in ('source.spm', 'target.spm', 'tokenizer_config.json', 'vocab.json', 'config.json', 'README.md'):
        shutil.copyfile(snapshot / name, tokenizer / name)
    shutil.rmtree(snapshot)
checksums = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in sorted(root.rglob('*')) if path.is_file()}
(root / 'checksums.json').write_text(json.dumps(checksums, indent=2) + '\n')
