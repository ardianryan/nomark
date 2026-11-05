"""Keep the single image slot occupied until its bounded HTTP response is sent."""
import asyncio
from starlette.responses import JSONResponse


class ImageResponseGate:
    def __init__(self, app, queue, timeout=120):
        self.app, self.queue, self.timeout = app, queue, timeout

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['path'] != '/api/image/process' or scope['method'] != 'POST':
            return await self.app(scope, receive, send)
        if self.queue.response_busy:
            return await JSONResponse({'ok': False, 'error': 'server_busy'}, status_code=503)(scope, receive, send)
        self.queue.response_busy = True
        started = False
        async def response_send(message):
            nonlocal started
            if message['type'] == 'http.response.start': started = True
            await send(message)
        try:
            async with asyncio.timeout(self.timeout):
                await self.app(scope, receive, response_send)
        except TimeoutError:
            if started:
                # A partial Content-Length response must be closed by the ASGI server.
                raise
            await JSONResponse({'ok': False, 'error': 'media_timeout'}, status_code=504)(scope, receive, send)
        finally:
            self.queue.response_busy = False
            self.queue.sweep()
