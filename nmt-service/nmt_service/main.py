"""Internal NMT API. No user text or parser diagnostics are logged."""
import asyncio
from contextlib import asynccontextmanager
import json
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .runtime import Runtime


class PrivacyHeaders:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        async def private_send(message):
            if message['type'] == 'http.response.start':
                message['headers'] = list(message.get('headers', [])) + [
                    (b'cache-control', b'no-store'), (b'x-content-type-options', b'nosniff')]
            await send(message)
        await self.app(scope, receive, private_send)


def create_app(runtime=None):
    runtime = runtime or Runtime(os.environ.get('NMT_MODEL_DIR', '/models'))

    @asynccontextmanager
    async def lifespan(app):
        async def maintain():
            while True:
                await asyncio.sleep(5)
                runtime.sweep()
        task = asyncio.create_task(maintain())
        try:
            yield
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            runtime.stop()

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

    app.add_middleware(PrivacyHeaders)

    @app.get('/health')
    async def health():
        ready = runtime.ready()
        return JSONResponse({'ok': ready, 'ready': ready}, status_code=200 if ready else 503)

    @app.get('/idle')
    async def idle():
        return {'ok': True, 'idle': not runtime.lock.locked()}

    @app.post('/paraphrase')
    async def paraphrase(request: Request):
        if not runtime.ready():
            return JSONResponse({'ok': False}, status_code=503)
        if request.headers.get('content-type', '').split(';')[0] != 'application/json':
            return JSONResponse({'ok': False}, status_code=415)
        try:
            raw = bytearray()
            async with asyncio.timeout(5):
                async for chunk in request.stream():
                    raw.extend(chunk)
                    if len(raw) > 65536:
                        return JSONResponse({'ok': False}, status_code=413)
            body = json.loads(raw)
            text = body.get('text') if isinstance(body, dict) else None
            language = body.get('language') if isinstance(body, dict) else None
            if not isinstance(text, str) or not text.strip() or language not in ('id', 'en'):
                return JSONResponse({'ok': False}, status_code=400)
            text.encode('utf-8')
            if len(text) > 5000:
                return JSONResponse({'ok': False}, status_code=413)
        except (ValueError, UnicodeError, RecursionError):
            return JSONResponse({'ok': False}, status_code=400)
        except TimeoutError:
            return JSONResponse({'ok': False}, status_code=408)
        try:
            return await runtime.process_text(text, language, request.is_disconnected)
        except TimeoutError:
            return JSONResponse({'ok': False}, status_code=504)
        except (RuntimeError, OSError, ValueError):
            return JSONResponse({'ok': False}, status_code=503)
        except asyncio.CancelledError:
            return JSONResponse({'ok': False}, status_code=499)

    return app


app = create_app()
