"""Image admission precedes multipart parsing; files remain local while queued."""
import asyncio
import secrets
from fastapi import Request

from nomark.image_client import INPUT_LIMIT, MediaClient, validate_name
from nomark.image_queue import ImageQueue
from nomark.jobs import JobError


def install(app):
    app.state.media = MediaClient()
    app.state.image_queue = ImageQueue()

    def token(request, processing=False):
        value = request.headers.get('x-nomark-reservation', '') if processing else request.headers.get('authorization', '')
        if not processing:
            if not value.startswith('Bearer '): raise JobError('queue_expired', 410)
            value = value[7:]
        if not value or len(value) > 100: raise JobError('queue_expired', 410)
        return value

    @app.get('/api/media/capabilities')
    async def capabilities():
        available = await app.state.media.available()
        if available and app.state.image_queue.blocked:
            available = await app.state.media.wait_idle()
            app.state.image_queue.blocked = not available
        return {'ok': True, 'available': available, 'formats': ['png', 'jpg', 'jpeg', 'webp'],
                'file_limit': INPUT_LIMIT, 'pixel_limit': 8_000_000, 'side_limit': 8192}

    @app.post('/api/media/queue')
    async def reserve(request: Request):
        if not app.state.media.url: raise JobError('media_unavailable', 503)
        return app.state.image_queue.reserve(request.scope['nomark.client'])

    @app.get('/api/media/queue')
    async def status(request: Request):
        return app.state.image_queue.status(token(request), request.scope['nomark.client'])

    @app.delete('/api/media/queue')
    async def cancel(request: Request):
        app.state.image_queue.cancel(token(request), request.scope['nomark.client'])
        return {'ok': True}

    @app.post('/api/image/process')
    async def process(request: Request):
        queue = app.state.image_queue
        with queue.claim(token(request, True), request.scope['nomark.client']):
            request.scope['nomark.image_claimed'] = True
            queue.task = asyncio.current_task()
            task = None
            job_id = secrets.token_hex(16)
            attempted = False
            finished = False
            try:
                if request.headers.get('content-type', '').split(';')[0] != 'multipart/form-data':
                    raise JobError('invalid_request', 415)
                async with asyncio.timeout(30), request.form(max_files=1, max_fields=0, max_part_size=INPUT_LIMIT) as form:
                    upload = form.get('file')
                    if len(form.multi_items()) != 1 or upload is None or not hasattr(upload, 'filename'):
                        raise JobError('invalid_request', 400)
                    name = validate_name(upload.filename)
                    content = await upload.read(INPUT_LIMIT + 1)
                    if not content: raise JobError('empty_file', 400)
                    if len(content) > INPUT_LIMIT: raise JobError('file_too_large', 413)
                attempted = True
                task = asyncio.create_task(app.state.media.process(content, name, job_id))
                while not task.done():
                    if await request.is_disconnected(): raise JobError('request_cancelled', 499)
                    await asyncio.sleep(.025)
                result = await task
                finished = True
                return result
            except asyncio.CancelledError:
                raise JobError('request_cancelled', 499) from None
            except TimeoutError:
                raise JobError('upload_timeout', 408) from None
            except JobError:
                raise
            except Exception as exc:
                from nomark.app import BodyLimit
                if isinstance(exc, BodyLimit): raise
                raise JobError('invalid_request', 400) from None
            finally:
                if task is not None:
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                if attempted and not finished:
                    queue.blocked = True
                    cleanup = asyncio.create_task(app.state.media.stop(job_id))
                    try:
                        stopped = await asyncio.shield(cleanup)
                    except asyncio.CancelledError:
                        stopped = await cleanup
                    queue.blocked = not stopped
