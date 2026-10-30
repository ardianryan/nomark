import hashlib
import importlib
import io
import json
from pathlib import Path

import pytest


@pytest.fixture
def promotion(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    module = importlib.import_module('promote_image')
    version = module.check()
    for key, value in {
        'CI_COMMIT_TAG': f'v{version}', 'CI_REGISTRY': 'registry.example.test',
        'CI_REGISTRY_IMAGE': 'registry.example.test/project/nomark',
        'CI_SERVER_URL': 'https://git.example.test',
        'CI_REGISTRY_USER': 'test-user', 'CI_REGISTRY_PASSWORD': 'test-password',
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'artifacts').mkdir()
    return module


def mock_registry(monkeypatch, module, *, expected_digest=None, latest=None):
    manifest = b'{"schemaVersion":2,"mediaType":"application/vnd.oci.image.index.v1+json","manifests":[]}'
    digest = 'sha256:' + hashlib.sha256(manifest).hexdigest()
    Path('artifacts/image-metadata.json').write_text(json.dumps({'containerimage.digest': expected_digest or digest}))
    calls = []

    def request(req, timeout):
        calls.append(req)
        if '/jwt/auth?' in req.full_url:
            content = b'{"token":"test-registry-token"}'
        elif req.get_method() == 'PUT':
            assert req.data == manifest
            content = b''
        elif req.full_url.endswith('/latest'):
            content = latest if latest is not None else manifest
        else:
            content = manifest
        response = io.BytesIO(content)
        response.headers = {'Content-Type': 'application/vnd.oci.image.index.v1+json'}
        return response

    monkeypatch.setattr(module, 'urlopen', request)
    return calls


def test_promotes_identical_tested_manifest(promotion, monkeypatch):
    calls = mock_registry(monkeypatch, promotion)
    promotion.promote()
    writes = [req for req in calls if req.get_method() == 'PUT']
    assert len(writes) == 1
    assert writes[0].full_url.endswith('/manifests/latest')


def test_build_digest_mismatch_prevents_registry_write(promotion, monkeypatch):
    calls = mock_registry(monkeypatch, promotion, expected_digest='sha256:incorrect')
    with pytest.raises(RuntimeError, match='does not match the tested build'):
        promotion.promote()
    assert not any(req.get_method() == 'PUT' for req in calls)


def test_promotion_detects_unexpected_latest_manifest(promotion, monkeypatch):
    mock_registry(monkeypatch, promotion, latest=b'other-manifest')
    with pytest.raises(RuntimeError, match='Latest manifest digest'):
        promotion.promote()


def test_branch_pipeline_cannot_promote(promotion, monkeypatch):
    monkeypatch.delenv('CI_COMMIT_TAG')
    monkeypatch.setattr(promotion, 'urlopen', lambda *a, **kw: pytest.fail('Registry was contacted'))
    with pytest.raises(RuntimeError, match='matching release tag'):
        promotion.promote()
