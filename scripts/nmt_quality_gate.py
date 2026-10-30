"""Block release promotion until all forty model samples are reviewed."""
import hashlib
import json
from pathlib import Path


def check_quality(data=None):
    root = Path(__file__).resolve().parents[1]
    if data is None:
        for name in ('docs/nmt-evaluation.json', 'docs/evaluations/alpha5-holdout.json'):
            check_quality(json.loads((root / name).read_text()))
        return
    rows = data['samples']
    if len(rows) != 40 or len({row['id'] for row in rows}) != 40:
        raise ValueError('NMT evaluation requires forty unique samples')
    if not all(sum(row['language'] == lang for row in rows) == 20 for lang in ('id', 'en')):
        raise ValueError('NMT evaluation requires twenty samples per language')
    if not all(row.get('reviewed') is True and row.get('critical_error') is False for row in rows):
        raise ValueError('NMT evaluation needs review or has critical meaning errors')
    if sum(row.get('language_acceptable') is True for row in rows) < 32:
        raise ValueError('NMT language acceptance below 80%')
    for language in ('id', 'en'):
        changed = [row for row in rows if row['language'] == language
                   and ''.join(row['input'].split()) != ''.join(row['output'].split())]
        if not changed:
            raise ValueError('NMT evaluation must include actual rewrites in both languages')
    if data.get('model_revisions') != json.loads((root / 'nmt-service/models.lock.json').read_text()):
        raise ValueError('Model evaluation is stale')
    files = ['nmt-service/build_models.py', 'nmt-service/build.lock', 'nmt-service/requirements.lock', 'nmt-service/nmt_service/pipeline.py']
    fingerprint = hashlib.sha256(b''.join((root / name).read_bytes() for name in files)).hexdigest()
    if data.get('engine_fingerprint') != fingerprint:
        raise ValueError('Tokenizer, converter or pipeline evaluation is stale')


if __name__ == '__main__':
    check_quality()
