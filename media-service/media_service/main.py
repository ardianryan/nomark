"""Private media API. Only fixed local image-processing operations are exposed."""
import asyncio
from contextlib import asynccontextmanager
import importlib.util
import re
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .pipeline import ImageError, MAX_INPUT, validate_name
from .runtime import Runtime


class PrivacyHeaders:
    def __init__(self, app): self.app = app
    async def __call__(self, scope, receive, send):
        async def private_send(message):
            if message['type'] == 'http.response.start':
                message['headers'] = list(message.get('headers', [])) + [(b'cache-control', b'no-store'), (b'x-content-type-options', b'nosniff')]
            await send(message)
        if scope['type'] != 'http':
            return await self.app(scope, receive, private_send)
        received = 0
        async def bounded_receive():
            nonlocal received
            message = await receive()
            received += len(message.get('body', b''))
            if received > MAX_INPUT + 1024 * 1024:
                raise ImageError('file_too_large', 413)
            return message
        await self.app(scope, bounded_receive, private_send)


def create_app(runtime=None):
    runtime = runtime or Runtime()
    @asynccontextmanager
    async def lifespan(app):
        async def maintain():
            while True:
                await asyncio.sleep(5)
                if runtime.blocked:
                    try: runtime.stop()
                    except RuntimeError: continue
                runtime.sweep()
        task = asyncio.create_task(maintain())
        try: yield
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            runtime.stop()
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.add_middleware(PrivacyHeaders)
    app.state.runtime = runtime

    @app.exception_handler(ImageError)
    async def error(request, exc):
        return JSONResponse({'ok': False, 'error': exc.code}, status_code=exc.status)

    @app.get('/health')
    async def health():
        ready = not runtime.blocked and time.monotonic() >= runtime.reject_until and all(importlib.util.find_spec(x) for x in ('remove_ai_watermarks', 'cv2', 'PIL'))
        return JSONResponse({'ok': bool(ready), 'ready': bool(ready)}, status_code=200 if ready else 503)

    @app.get('/idle')
    async def idle():
        return {'ok': True, 'idle': not runtime.lock.locked() and not runtime.blocked and time.monotonic() >= runtime.reject_until}

    @app.delete('/jobs/{job_id}')
    async def cancel(job_id: str):
        if not re.fullmatch('[a-f0-9]{32}', job_id):
            raise ImageError('invalid_request', 400)
        try:
            stopped = runtime.cancel(job_id)
        except RuntimeError:
            raise ImageError('media_unavailable', 503) from None
        return {'ok': True, 'stopped': stopped}

    @app.post('/process')
    async def process(request: Request):
        job_id = request.headers.get('x-nomark-job', '')
        if not re.fullmatch('[a-f0-9]{32}', job_id):
            raise ImageError('invalid_request', 400)
        if runtime.lock.locked() or runtime.blocked:
            raise ImageError('media_unavailable', 503)
        try:
            async with asyncio.timeout(30), request.form(max_files=1, max_fields=0, max_part_size=MAX_INPUT) as form:
                upload = form.get('file')
                if len(form.multi_items()) != 1 or upload is None or not hasattr(upload, 'filename'):
                    raise ImageError('invalid_request', 400)
                name = validate_name(upload.filename)
                data = await upload.read(MAX_INPUT + 1)
                if not data: raise ImageError('empty_file', 400)
                if len(data) > MAX_INPUT: raise ImageError('file_too_large', 413)
            return await runtime.process_image(data, name, job_id, request.is_disconnected)
        except ImageError:
            raise
        except TimeoutError:
            raise ImageError('upload_timeout', 408) from None
        except asyncio.CancelledError:
            raise ImageError('request_cancelled', 499) from None
        except Exception:
            raise ImageError('processing_failed') from None
    return app


app = create_app()
