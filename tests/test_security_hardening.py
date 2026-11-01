import asyncio
import importlib
import os
from pathlib import Path
import sys
import time
import types

import httpx
import pytest

from nomark.app import Guard, create_app
from nomark.cleanup import cleanup_stale_jobs
from nomark.engine import process_file, process_text
from nomark.media import clean_media
from nomark import upstream


@pytest.fixture
def case_root(request):
    configured = os.environ.get('NOMARK_SECURITY_TEST_ROOT')
    root = Path(configured) / request.node.name if configured else request.getfixturevalue('tmp_path')
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_deep_json_returns_400_and_releases_capacity():
    class NoJobs:
        concurrency = 2
    app = create_app(jobs=NoJobs())
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            raw = b'{"text":' + b'[' * 2000 + b'0' + b']' * 2000 + b'}'
            response = await client.post('/api/text/process', content=raw, headers={'Content-Type': 'application/json'})
            assert response.status_code == 400
            assert response.json()['error'] == 'invalid_request'
            assert app.state.admission.active == 0
    asyncio.run(scenario())


def test_forwarded_addresses_keep_separate_buckets(monkeypatch):
    monkeypatch.setenv('NOMARK_TRUSTED_PROXIES', '10.0.0.0/8')
    async def application(scope, receive, send):
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await send({'type': 'http.response.body', 'body': b''})
    guard = Guard(application)
    async def request(peer, forwarded):
        statuses = []
        async def send(message):
            if message['type'] == 'http.response.start':
                statuses.append(message['status'])
        async def receive():
            return {'type': 'http.request', 'body': b''}
        scope = {'type': 'http', 'path': '/api/check', 'method': 'POST', 'client': (peer, 1),
                 'headers': [(b'x-forwarded-for', forwarded.encode())]}
        await guard(scope, receive, send)
        return statuses[0]
    async def scenario():
        for _ in range(20):
            assert await request('10.0.0.1', ', , ') == 200
        assert await request('10.0.0.1', '') == 429
        assert await request('10.0.0.2', ', , ') == 200
        assert await request('10.0.0.3', 'not-an-ip') == 200
        for _ in range(19):
            assert await request('10.0.0.3', '') == 200
        assert await request('10.0.0.3', 'not-an-ip') == 429
        assert await request('10.0.0.1', '2001:db8::1') == 200
        assert await request('192.0.2.1', '2001:db8::1') == 200
        assert len(guard.requests) == 5
    asyncio.run(scenario())


def test_nomark_proxy_only_accepts_sanitized_forwarded_address(monkeypatch):
    monkeypatch.setenv('NOMARK_TRUSTED_PROXIES', '10.1.0.18/32')
    async def application(scope, receive, send):
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await send({'type': 'http.response.body', 'body': b''})
    guard = Guard(application)
    async def request(peer, forwarded):
        statuses = []
        async def send(message):
            if message['type'] == 'http.response.start':
                statuses.append(message['status'])
        async def receive():
            return {'type': 'http.request', 'body': b''}
        scope = {'type': 'http', 'path': '/api/paraphrase/queue', 'method': 'POST',
                 'client': (peer, 1), 'headers': [(b'x-forwarded-for', forwarded.encode())]}
        await guard(scope, receive, send)
        return statuses[0]
    async def scenario():
        for _ in range(5):
            assert await request('10.1.0.18', '203.0.113.10') == 200
        assert await request('10.1.0.18', '203.0.113.10') == 429
        assert await request('10.1.0.18', '203.0.113.11') == 200
        # An unrelated peer cannot select the rate bucket using a forged header.
        assert await request('10.1.0.19', '203.0.113.10') == 200
        for _ in range(4):
            assert await request('10.1.0.19', '203.0.113.11') == 200
        assert await request('10.1.0.19', '203.0.113.12') == 429
    asyncio.run(scenario())


def test_cleanup_keeps_recent_jobs_and_symlink_targets(case_root):
    root = case_root / 'work'
    root.mkdir(exist_ok=True)
    stale, recent = root / 'nomark-old', root / 'nomark-new'
    stale.mkdir(exist_ok=True)
    recent.mkdir(exist_ok=True)
    (stale / 'input').write_text('old')
    (recent / 'input').write_text('new')
    outside = case_root / 'outside'
    outside.mkdir(exist_ok=True)
    (outside / 'keep').write_text('must remain')
    (root / 'nomark-link').symlink_to(outside, target_is_directory=True)
    os.utime(stale, (time.time() - 600,) * 2)
    cleanup_stale_jobs(root)
    assert not stale.exists()
    assert (recent / 'input').read_text() == 'new'
    assert (outside / 'keep').read_text() == 'must remain'
    assert (root / 'nomark-link').is_symlink()


def test_cleanup_rejects_symlink_swap_during_deletion(case_root, monkeypatch):
    root = case_root / 'work'
    root.mkdir(exist_ok=True)
    stale = root / 'nomark-race'
    stale.mkdir(exist_ok=True)
    outside = case_root / 'outside'
    outside.mkdir(exist_ok=True)
    (outside / 'keep').write_text('must remain')
    os.utime(stale, (time.time() - 600,) * 2)
    original_stat = os.stat
    switched = False
    def swapping_stat(path, *args, **kwargs):
        nonlocal switched
        result = original_stat(path, *args, **kwargs)
        if path == 'nomark-race' and kwargs.get('follow_symlinks') is False and not switched:
            switched = True
            stale.rename(root / 'parked')
            stale.symlink_to(outside, target_is_directory=True)
        return result
    monkeypatch.setattr(os, 'stat', swapping_stat)
    cleanup_stale_jobs(root)
    assert switched
    assert (outside / 'keep').read_text() == 'must remain'
    assert stale.is_symlink()


def test_cleanup_does_not_open_symlinked_work_root(case_root):
    outside = case_root / 'outside'
    outside.mkdir(exist_ok=True)
    stale = outside / 'nomark-old'
    stale.mkdir(exist_ok=True)
    (stale / 'keep').write_text('must remain')
    os.utime(stale, (time.time() - 600,) * 2)
    link = case_root / 'work-link'
    link.symlink_to(outside, target_is_directory=True)
    cleanup_stale_jobs(link)
    assert (stale / 'keep').read_text() == 'must remain'


def test_upstream_loader_ignores_unrelated_global_modules(monkeypatch):
    rogue = types.ModuleType('common')
    rogue.looks_binary = lambda value: pytest.fail('Loaded unrelated common module')
    monkeypatch.setitem(sys.modules, 'common', rogue)
    before = list(sys.path)
    assert upstream.load('common') is not rogue
    importlib.reload(upstream)
    assert list(sys.path) == before
    assert sys.modules['common'] is rogue
    assert process_text('hello\u200b')['cleaned_text'] == 'hello'
    assert upstream.text_unicode.__file__ == str(upstream.SCRIPTS / 'text_unicode.py')
    assert upstream.container_meta.safe_write_bytes is upstream.common.safe_write_bytes


def test_scoped_upstream_imports_work_in_container_cleaning(case_root, monkeypatch):
    names = (f'slot{index:02}' for index in range(32))
    monkeypatch.setattr(upstream.common.tempfile, '_get_candidate_names', lambda: names)
    source = case_root / 'draft.md'
    source.write_text('Hello\u200bworld')
    result = process_file(source, source.name, case_root)
    assert result['status'] == 'cleaned'


def test_image_cleaner_refuses_symlink_destination(case_root):
    source = Path(__file__).parent / 'fixtures/media/sample.png'
    outside = case_root / 'keep'
    outside.write_text('must remain')
    destination = case_root / 'output.png'
    destination.symlink_to(outside)
    with pytest.raises(OSError, match='symlink'):
        clean_media(source, destination, source.read_bytes(), '.png')
    assert outside.read_text() == 'must remain'


def test_health_returns_only_public_readiness_fields():
    class NoJobs:
        concurrency = 2
    app = create_app(jobs=NoJobs())
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            response = await client.get('/health')
            assert response.status_code == 200
            assert set(response.json()) == {'ok', 'version', 'engine_available', 'pdf_ready'}
            assert response.headers['cache-control'] == 'no-store'
    asyncio.run(scenario())
