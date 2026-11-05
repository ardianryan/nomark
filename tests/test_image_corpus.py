import json
from scripts.evaluate_media import evaluate


def test_fixed_corpus_has_no_false_positives_or_changes_outside_masks(tmp_path):
    evaluate(tmp_path)
    report=json.loads((tmp_path/'evaluation.json').read_text())
    rows=report['samples']
    assert len(rows)==30
    assert sum(r['category']=='clean' for r in rows)==10
    assert sum(r['category']=='unsupported' for r in rows)==5
    assert sum(r['category']=='supported' for r in rows)==15
    assert all(r['changed_outside_mask']==0 for r in rows)
