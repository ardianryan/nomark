import asyncio
import base64
import io

import httpx
import pytest
from PIL import Image

from nomark.app import create_app
from nomark.image_client import MediaClient
from nomark.image_queue import ImageQueue
from nomark.jobs import JobError


class NoJobs:
    concurrency = 2


def payload():
    out = io.BytesIO(); Image.new('RGBA', (4, 3), 'green').save(out, 'PNG'); data = out.getvalue()
    return {'ok': True, 'cleaned_base64': base64.b64encode(data).decode(), 'width': 4, 'height': 3,
            'bytes_in': 3, 'bytes_out': len(data), 'elapsed_ms': 10, 'visual_status': 'no_watermark',
            'marks': [], 'metadata_removed': False, 'normalized': True}


@pytest.mark.parametrize('mutation', ['good','base64','dimensions','bytes','marks','status','metadata','json','redirect','error'])
def test_media_client_validates_every_response_field(mutation):
    async def handler(request):
        body = payload()
        if mutation == 'base64': body['cleaned_base64'] = '@@@'
        if mutation == 'dimensions': body['width'] = 999
        if mutation == 'bytes': body['bytes_out'] = 1
        if mutation == 'marks': body['marks'] = [{'key': '<script>', 'label': 'bad', 'status': 'cleaned'}]
        if mutation == 'status': body['visual_status'] = 'cleaned'
        if mutation == 'metadata': body['metadata_removed'] = 'true'
        if mutation == 'json': return httpx.Response(200, content=b'['*5000)
        if mutation == 'redirect': return httpx.Response(302, headers={'Location':'http://unexpected'})
        if mutation == 'error': return httpx.Response(422, json={'error': '/private/path/not_forwarded'})
        return httpx.Response(200, json=body)
    async def scenario():
        client = MediaClient('http://media', transport=httpx.MockTransport(handler))
        if mutation == 'good':
            result = await client.process(b'abc', 'example.webp', 'a'*32)
            assert result['cleaned_name'] == 'example.cleaned.png'
            assert result['status'] == 'unchanged'
            assert result['processed_by'] == 'server'
        else:
            with pytest.raises(JobError) as caught: await client.process(b'abc','image.png','a'*32)
            assert caught.value.code == 'media_failed'
    asyncio.run(scenario())


def test_media_queue_ownership_capacity_expiry_and_type_isolation():
    now = [0]; q = ImageQueue(clock=lambda:now[0]); first = q.reserve('a')
    assert first['state'] == 'ready'
    with pytest.raises(JobError): q.reserve('a')
    second = q.reserve('b'); q.reserve('c')
    with pytest.raises(JobError): q.reserve('d')
    with pytest.raises(JobError): q.status(first['token'],'b')
    with q.claim(first['token'],'a'):
        assert q.status(second['token'],'b')['state'] == 'waiting'
    assert q.status(second['token'],'b')['state'] == 'ready'
    now[0] = 200
    with pytest.raises(JobError): q.status(second['token'],'b')


@pytest.mark.parametrize('name,data,status', [('image.png',b'abc',200),('../image.png',b'abc',400),
    ('image.svg',b'abc',415),('image.png',b'',400)])
def test_image_api_reservation_before_upload_and_validation(name,data,status):
    app = create_app(jobs=NoJobs())
    class Fake:
        url='http://media'
        async def process(self,*args): return {'ok':True,'kind':'image'}
        async def stop(self,*args): return True
    app.state.media=Fake()
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            assert (await client.post('/api/image/process',content=b'no parsing')).status_code == 410
            ticket=(await client.post('/api/media/queue')).json()['token']
            # A media ticket is not a PDF or NMT reservation.
            assert (await client.get('/api/paraphrase/queue',headers={'Authorization':'Bearer '+ticket})).status_code == 410
            response=await client.post('/api/image/process',files={'file':(name,data)},headers={'X-NoMark-Reservation':ticket})
            assert response.status_code==status
            assert response.headers['x-nomark-reservation-consumed']=='1'
            assert response.headers['cache-control']=='no-store'
            assert app.state.image_queue.running is None
            assert not app.state.image_queue.tickets
            assert app.state.admission.active == 0
    asyncio.run(scenario())


def test_image_rate_limit_counts_reservations_not_polls():
    app=create_app(jobs=NoJobs())
    class Fake: url='http://media'
    app.state.media=Fake()
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
            for _ in range(5):
                r=await c.post('/api/media/queue'); assert r.status_code==200; token=r.json()['token']
                for _ in range(10): assert (await c.get('/api/media/queue',headers={'Authorization':'Bearer '+token})).status_code==200
                assert (await c.delete('/api/media/queue',headers={'Authorization':'Bearer '+token})).status_code==200
            limited=await c.post('/api/media/queue'); assert limited.status_code==429
            assert int(limited.headers['Retry-After'])>0
            assert (await c.post('/api/queue')).status_code==200
    asyncio.run(scenario())


def test_failed_stop_blocks_media_admission():
    app=create_app(jobs=NoJobs())
    class Fake:
        url='http://media'
        async def process(self,*args): raise JobError('media_timeout',504)
        async def stop(self,*args): return False
    app.state.media=Fake()
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
            token=(await c.post('/api/media/queue')).json()['token']
            r=await c.post('/api/image/process',files={'file':('a.png',b'abc')},headers={'X-NoMark-Reservation':token})
            assert r.status_code==504
            assert app.state.image_queue.blocked
            assert (await c.post('/api/media/queue')).status_code==503
    asyncio.run(scenario())


def test_repeated_cancel_cannot_interrupt_worker_cleanup():
    app=create_app(jobs=NoJobs())
    class Fake:
        url='http://media'
        def __init__(self): self.stopping=asyncio.Event();self.release=asyncio.Event()
        async def process(self,*args): await asyncio.sleep(30)
        async def stop(self,*args):
            self.stopping.set();await self.release.wait();return True
    async def scenario():
        service=Fake();app.state.media=service
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
            token=(await c.post('/api/media/queue')).json()['token']
            processing=asyncio.create_task(c.post('/api/image/process',files={'file':('a.png',b'data')},headers={'X-NoMark-Reservation':token}))
            await asyncio.sleep(.05)
            for _ in range(2):
                assert (await c.delete('/api/media/queue',headers={'Authorization':'Bearer '+token})).status_code==200
            await service.stopping.wait()
            assert app.state.image_queue.running is not None and app.state.image_queue.blocked
            service.release.set()
            assert (await processing).status_code==499
            assert app.state.image_queue.running is None and not app.state.image_queue.blocked
    asyncio.run(scenario())


def test_response_backpressure_holds_image_admission():
    from nomark.image_response import ImageResponseGate
    async def scenario():
        queue=ImageQueue();ready=queue.reserve('first');awaiting_send=asyncio.Event();allow_send=asyncio.Event()
        async def app(scope,receive,send):
            with queue.claim(ready['token'],'first'):
                pass
            await send({'type':'http.response.start','status':200,'headers':[]})
            await send({'type':'http.response.body','body':b'bounded png response'})
        async def send(message):
            if message['type']=='http.response.body':
                awaiting_send.set();await allow_send.wait()
        async def receive():return {'type':'http.request','body':b''}
        task=asyncio.create_task(ImageResponseGate(app,queue)({'type':'http','method':'POST','path':'/api/image/process'},receive,send))
        await awaiting_send.wait()
        second=queue.reserve('second')
        assert second['state']=='waiting' and queue.response_busy
        allow_send.set();await task
        assert queue.status(second['token'],'second')['state']=='ready'
    asyncio.run(scenario())


def test_stalled_image_response_has_a_deadline_and_releases_capacity():
    from nomark.image_response import ImageResponseGate
    async def scenario():
        queue=ImageQueue()
        async def app(scope,receive,send):
            await send({'type':'http.response.start','status':200,'headers':[]})
            await send({'type':'http.response.body','body':b'result'})
        async def stalled_send(message):
            if message['type']=='http.response.body': await asyncio.sleep(30)
        async def receive():return {'type':'http.request','body':b''}
        with pytest.raises(TimeoutError):
            await ImageResponseGate(app,queue,timeout=.05)({'type':'http','method':'POST','path':'/api/image/process'},receive,stalled_send)
        assert not queue.response_busy
        assert queue.reserve('next')['state']=='ready'
    asyncio.run(scenario())


def test_media_response_stream_stops_at_the_size_boundary(monkeypatch):
    import json
    import nomark.image_client as module
    monkeypatch.setattr(module,'RESPONSE_LIMIT',128)
    raw=json.dumps(payload()).encode();seen=[]
    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            for offset in range(0,len(raw),32):
                seen.append(offset);yield raw[offset:offset+32]
    async def transport(request):return httpx.Response(200,stream=Stream())
    async def scenario():
        with pytest.raises(JobError) as caught:
            await MediaClient('http://media',transport=httpx.MockTransport(transport)).process(b'abc','a.png','a'*32)
        assert caught.value.code=='media_failed'
        assert len(seen)*32<len(raw)
    asyncio.run(scenario())
