"""Public optional paraphrase routes; admission always precedes text ingestion."""
import asyncio
import json
import time

from fastapi import Request

from nomark.jobs import JobError
from nomark.paraphrase import BODY_LIMIT, LIMIT, NMTClient
from nomark.paraphrase_queue import ParaphraseQueue


def install(app):
    app.state.nmt = NMTClient()
    app.state.paraphrase_queue = ParaphraseQueue()

    def identity(request):
        return request.scope['nomark.client']

    def token(request, processing=False):
        value = request.headers.get('x-nomark-reservation', '') if processing else request.headers.get('authorization', '')
        if not processing:
            if not value.startswith('Bearer '):
                raise JobError('queue_expired', 410)
            value = value[7:]
        if not value or len(value) > 100:
            raise JobError('queue_expired', 410)
        return value

    @app.get('/api/paraphrase/capabilities')
    async def capabilities():
        available = await app.state.nmt.available()
        if available and app.state.paraphrase_queue.blocked:
            available = await app.state.nmt.wait_idle()
            app.state.paraphrase_queue.blocked = not available
        return {'ok': True, 'available': available, 'languages': ['id', 'en'], 'text_limit': LIMIT}

    @app.post('/api/paraphrase/queue')
    async def reserve(request: Request):
        if not app.state.nmt.url:
            raise JobError('paraphrase_unavailable', 503)
        return app.state.paraphrase_queue.reserve(identity(request))

    @app.get('/api/paraphrase/queue')
    async def status(request: Request):
        return app.state.paraphrase_queue.status(token(request), identity(request))

    @app.delete('/api/paraphrase/queue')
    async def cancel(request: Request):
        app.state.paraphrase_queue.cancel(token(request), identity(request))
        return {'ok': True}

    @app.post('/api/text/paraphrase')
    async def process(request: Request):
        queue = app.state.paraphrase_queue
        with queue.claim(token(request, True), identity(request)):
            if request.headers.get('content-type', '').split(';')[0] != 'application/json':
                raise JobError('invalid_request', 415)
            try:
                raw = bytearray()
                async with asyncio.timeout(5):
                    async for chunk in request.stream():
                        raw.extend(chunk)
                        if len(raw) > BODY_LIMIT:
                            raise JobError('text_too_large', 413)
                body = json.loads(raw)
                text = body.get('text') if isinstance(body, dict) else None
                language = body.get('language') if isinstance(body, dict) else None
                if not isinstance(text, str) or not text.strip():
                    raise JobError('empty_text', 400)
                if len(text) > LIMIT:
                    raise JobError('text_too_large', 413)
                if language not in ('id', 'en'):
                    raise JobError('unsupported_language', 400)
                text.encode('utf-8')
            except (ValueError, UnicodeError, RecursionError):
                raise JobError('invalid_request', 400) from None
            except TimeoutError:
                raise JobError('upload_timeout', 408) from None
            task = asyncio.create_task(app.state.nmt.process(text, language))
            queue.task = task
            started = time.monotonic()
            try:
                while not task.done():
                    if await request.is_disconnected():
                        raise JobError('request_cancelled', 499)
                    await asyncio.sleep(0.025)
                return {**await task, 'elapsed_ms': round((time.monotonic() - started) * 1000)}
            except asyncio.CancelledError:
                raise JobError('request_cancelled', 499) from None
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                if task.cancelled():
                    queue.blocked = not await app.state.nmt.wait_idle()
