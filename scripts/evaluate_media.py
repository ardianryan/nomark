"""Evaluate the fixed synthetic media corpus using the real upstream adapter."""
import argparse
import hashlib
import json
from pathlib import Path
import time

import cv2
import numpy as np
from PIL import Image
import remove_ai_watermarks.region_eraser as eraser
from media_service.pipeline import process, inspect_image, normalized


def evaluate(output):
    root = Path(__file__).resolve().parents[1]
    fixtures = root / 'tests/fixtures/images'
    manifest = json.loads((fixtures / 'manifest.json').read_text())
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    original_erase = eraser.erase
    for row in manifest['samples']:
        masks = []
        def capture(image, *, mask=None, **kwargs):
            if mask is not None: masks.append(mask.copy())
            return original_erase(image, mask=mask, **kwargs)
        eraser.erase = capture
        source = fixtures / row['file']
        if hashlib.sha256(source.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Media evaluation corpus changed')
        target = output / row['file']
        started = time.monotonic()
        try:
            report = process(source, row['file'], target)
        finally:
            eraser.erase = original_erase
        before, orientation, icc, _ = inspect_image(source, row['file'])
        if orientation != 1 or icc:
            raise ValueError('Corpus pixel checks require untagged upright fixtures')
        before_array = np.asarray(normalized(before, orientation, icc))
        after = np.asarray(Image.open(target).convert('RGBA'))
        changed = np.any(before_array != after, axis=2)
        union = np.zeros(changed.shape, dtype=bool)
        for mask in masks: union |= mask > 0
        outside = int(np.count_nonzero(changed & ~union))
        found = [m['key'] for m in report['marks']]
        rows.append({**row, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                     **report, 'elapsed_ms': round((time.monotonic() - started)*1000),
                     'changed_pixels': int(changed.sum()), 'changed_outside_mask': outside,
                     'expected_found': row.get('expected_mark') in found if row['category'] == 'supported' else None,
                     'reviewed': False})
        print(row['file'], report['visual_status'], found, outside, flush=True)
    result = {'version': '0.1.0-alpha.8', 'upstream_commit': manifest['upstream_commit'],
              'synthetic': True, 'visual_review_complete': False, 'samples': rows}
    (output / 'evaluation.json').write_text(json.dumps(result, indent=2)+'\n')
    if any(r['changed_outside_mask'] or (r['category'] in ('clean', 'unsupported') and r['marks']) or (r['category'] == 'supported' and not r['expected_found'] and r['expected_mark'] not in manifest['allowed_misses']) for r in rows):
        raise SystemExit('Media corpus detected a false positive or out-of-mask changes')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, required=True)
    evaluate(parser.parse_args().output)
