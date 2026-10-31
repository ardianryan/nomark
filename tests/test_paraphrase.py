import asyncio
import json

import httpx
import pytest

from nomark.app import create_app
from nomark.jobs import JobError
from nomark.paraphrase import NMTClient
from nomark.paraphrase_queue import ParaphraseQueue


class NoJobs:
    concurrency = 2


def test_nmt_queue_ownership_expiry_and_independent_capacity():
    now = [0]
    q = ParaphraseQueue(clock=lambda: now[0])
    first = q.reserve('a')
    assert first['state'] == 'ready'
    with pytest.raises(JobError): q.reserve('a')
    second = q.reserve('b')
    q.reserve('c')
    with pytest.raises(JobError): q.reserve('d')
    with pytest.raises(JobError): q.status(first['token'], 'b')
    with pytest.raises(JobError):
        with q.claim(second['token'], 'b'): pass
    with q.claim(first['token'], 'a'):
        assert q.status(second['token'], 'b')['state'] == 'waiting'
    assert q.status(second['token'], 'b')['state'] == 'ready'
    now[0] = 200
    with pytest.raises(JobError): q.status(second['token'], 'b')
    assert q.reserve('a')['state'] == 'ready'


@pytest.mark.parametrize('kind', ['timeout', 'network', 'json', 'oversized', 'shape', 'status', 'good'])
def test_nmt_client_bounds_and_errors(kind):
    async def transport(request):
        if kind == 'timeout': raise httpx.ReadTimeout('synthetic')
        if kind == 'network': raise httpx.ConnectError('synthetic')
        if kind == 'json': return httpx.Response(200, content=b'not-json')
        if kind == 'oversized': return httpx.Response(200, content=b'x' * (1024 * 1024 + 1))
        if kind == 'shape': return httpx.Response(200, json={'ok': True})
        if kind == 'status': return httpx.Response(500, json={'error': 'do_not_forward'})
        return httpx.Response(200, json={'ok': True, 'paraphrased_text': 'Result.', 'status': 'paraphrased', 'language': 'en', 'warnings': ['review_required']})
    async def scenario():
        client = NMTClient('http://nmt', transport=httpx.MockTransport(transport))
        if kind == 'good':
            assert (await client.process('Original.', 'en'))['processed_by'] == 'server'
        else:
            with pytest.raises(JobError) as error: await client.process('Original.', 'en')
            assert error.value.code != 'do_not_forward'
        with pytest.raises(JobError): await NMTClient('').process('Original.', 'en')
    asyncio.run(scenario())


@pytest.mark.parametrize('body,status', [({'text': '', 'language': 'en'}, 400),
    ({'text': 'text', 'language': 'xx'}, 400), ({'text': 'x' * 5001, 'language': 'en'}, 413),
    ({'text': '\ud800', 'language': 'id'}, 400), ({'text': 'text', 'language': 'id'}, 200)])
def test_paraphrase_api_validation_and_ticket_consumption(body, status):
    app = create_app(jobs=NoJobs())
    class Fake:
        url = 'http://nmt'
        async def process(self, text, language):
            return {'ok': True, 'status': 'paraphrased', 'paraphrased_text': 'Hasil.', 'language': language}
    app.state.nmt = Fake()
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            denied = await client.post('/api/text/paraphrase', content=b'not read')
            assert denied.status_code == 410
            ticket = (await client.post('/api/paraphrase/queue')).json()['token']
            response = await client.post('/api/text/paraphrase', content=json.dumps(body), headers={'Content-Type': 'application/json', 'X-NoMark-Reservation': ticket})
            assert response.status_code == status
            assert response.headers['cache-control'] == 'no-store'
            assert app.state.admission.active == 0
            assert app.state.paraphrase_queue.running is None
            assert not app.state.paraphrase_queue.tickets
    asyncio.run(scenario())


def test_optional_nmt_and_separate_rate_bucket():
    app = create_app(jobs=NoJobs())
    app.state.nmt = NMTClient('')
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            assert (await client.get('/api/paraphrase/capabilities')).json()['available'] is False
            for _ in range(5):
                assert (await client.post('/api/paraphrase/queue')).status_code == 503
            assert (await client.post('/api/paraphrase/queue')).status_code == 429
            assert (await client.get('/health')).status_code == 200
            assert (await client.post('/api/queue')).status_code == 200
    asyncio.run(scenario())


def test_cancelled_inference_waits_for_idle_before_releasing_admission():
    app = create_app(jobs=NoJobs())
    class Fake:
        url = 'http://nmt'
        def __init__(self): self.checked = False
        async def process(self, text, language):
            await asyncio.sleep(30)
        async def wait_idle(self):
            assert app.state.paraphrase_queue.running is not None
            self.checked = True
            return False
    fake = Fake()
    app.state.nmt = fake
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            ticket = (await client.post('/api/paraphrase/queue')).json()['token']
            task = asyncio.create_task(client.post('/api/text/paraphrase', json={'text':'hello','language':'en'}, headers={'X-NoMark-Reservation':ticket}))
            for _ in range(100):
                if app.state.paraphrase_queue.task is not None: break
                await asyncio.sleep(.01)
            await client.delete('/api/paraphrase/queue', headers={'Authorization':f'Bearer {ticket}'})
            assert (await task).status_code == 499
            assert fake.checked
            assert app.state.paraphrase_queue.blocked
            assert (await client.post('/api/paraphrase/queue')).status_code == 503
    asyncio.run(scenario())


def test_quality_gate_checks_meaning_language_and_source_freshness(monkeypatch):
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    from nmt_quality_gate import check_quality
    data = json.loads((Path(__file__).resolve().parents[1] / 'docs/nmt-evaluation.json').read_text())
    for row in data['samples']:
        row.update(reviewed=True, critical_error=False, language_acceptable=True)
    check_quality(data)
    data['samples'][0]['critical_error'] = True
    with pytest.raises(ValueError, match='critical meaning errors'): check_quality(data)
    data['samples'][0]['critical_error'] = False
    for row in data['samples'][:9]: row['language_acceptable'] = False
    with pytest.raises(ValueError, match='below 80%'): check_quality(data)
    for row in data['samples']: row['language_acceptable'] = True
    data['engine_fingerprint'] = 'stale'
    with pytest.raises(ValueError, match='stale'): check_quality(data)


def test_quality_gate_does_not_accept_retained_inputs_as_rewrites(monkeypatch):
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root / 'scripts'))
    from nmt_quality_gate import check_quality
    data = json.loads((root / 'docs/nmt-evaluation.json').read_text())
    for row in data['samples']:
        row['output'] = row['input'].replace(' ', '  ')
    with pytest.raises(ValueError, match='actual rewrites'):
        check_quality(data)


@pytest.mark.parametrize('malformation', ['none', 'offset', 'bool', 'overlap', 'alternative', 'surrogate', 'many'])
def test_optional_metadata_is_validated_without_losing_text(malformation):
    from nomark.paraphrase import validate_edits
    source, output = '🙂 cannot', "🙂 can't"
    edit = {'id': 'one', 'input_start': 2, 'input_end': 8, 'output_start': 2,
            'output_end': 7, 'before': 'cannot', 'after': "can't", 'alternatives': ['can not']}
    value = [edit]
    if malformation == 'offset': edit['output_start'] = 3
    if malformation == 'bool': edit['input_start'] = True
    if malformation == 'overlap': value.append(dict(edit, id='two'))
    if malformation == 'alternative': edit['alternatives'] = [dict(text='bad')]
    if malformation == 'surrogate': edit['alternatives'] = ['\ud800']
    if malformation == 'many': value *= 257
    assert bool(validate_edits(value, source, output)) == (malformation == 'none')


def test_client_keeps_valid_output_when_optional_metadata_is_malformed():
    async def scenario():
        def response(request):
            return httpx.Response(200, json={'ok': True, 'paraphrased_text': "We can't proceed.",
                'language': 'en', 'status': 'paraphrased', 'warnings': ['review_required'],
                'edits': [{'output_start': -1, 'alternatives': ['untrusted']}]})
        result = await NMTClient('http://nmt', transport=httpx.MockTransport(response)).process('We cannot proceed.', 'en')
        assert result['paraphrased_text'] == "We can't proceed."
        assert result['edits'] == []
    asyncio.run(scenario())
