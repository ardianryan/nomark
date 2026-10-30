from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from contextlib import asynccontextmanager
import ipaddress
import hashlib
import hmac
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, Response

from nomark import __version__
from nomark.jobs import JobError, Jobs
from nomark.admission import Admission
from nomark.assets import Assets
from nomark.cleanup import cleanup_stale_jobs
from nomark.policies import render_policy
from nomark.seo import SITE, render_index, sitemap, llms_index, llms_full

ROOT = Path(__file__).resolve().parents[1]
FILE_LIMIT = 20 * 1024 * 1024
TEXT_LIMIT = 200_000
BODY_LIMIT = FILE_LIMIT + 1024 * 1024
ALLOWED = {".txt", ".md", ".markdown", ".html", ".htm", ".pdf", ".docx", ".xlsx", ".pptx", ".odt", ".epub"}
CSP = "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; worker-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"


class BodyLimit(Exception):
    pass


class Guard:
    def __init__(self, app):
        self.app = app
        self.requests = defaultdict(deque)
        self.salt = os.urandom(32)
        self.last_sweep = 0
        self.trusted = [ipaddress.ip_network(x.strip()) for x in os.environ.get("NOMARK_TRUSTED_PROXIES", "").split(",") if x.strip()]

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope["path"]
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        is_api = path.startswith("/api/")
        async def secure_send(message):
            if message["type"] == "http.response.start":
                extra = [(b"content-security-policy", CSP.encode()), (b"x-content-type-options", b"nosniff"), (b"referrer-policy", b"no-referrer"), (b"permissions-policy", b"camera=(), microphone=(), geolocation=()")]
                if is_api or path == "/health":
                    extra.append((b"cache-control", b"no-store"))
                    extra.append((b"x-robots-tag", b"noindex, nofollow"))
                elif path.startswith(("/static/vendor/engines/", "/static/vendor/pyodide/314.0.7/")):
                    extra.append((b"cache-control", b"public, max-age=31536000, immutable"))
                elif path.startswith("/static/"):
                    extra.append((b"cache-control", b"no-cache"))
                message["headers"] = list(message.get("headers", [])) + extra
            await send(message)
        async def reject(code, status):
            await JSONResponse({"ok": False, "error": code}, status_code=status)(scope, receive, secure_send)
        if is_api:
            if headers.get("sec-fetch-site") == "cross-site":
                return await reject("cross_origin", 403)
            if "origin" in headers:
                from urllib.parse import urlsplit
                if urlsplit(headers["origin"]).netloc != headers.get("host"):
                    return await reject("cross_origin", 403)
            address = (scope.get("client") or ("unknown", 0))[0]
            try:
                if any(ipaddress.ip_address(address) in network for network in self.trusted):
                    forwarded = headers.get("x-forwarded-for", "").split(",")[-1].strip()
                    if forwarded:
                        address = str(ipaddress.ip_address(forwarded))
            except ValueError:
                pass
            address = hmac.new(self.salt, address.encode(), hashlib.sha256).hexdigest()
            scope['nomark.client'] = address
            now = time.monotonic()
            if now - self.last_sweep > 60 or len(self.requests) > 10_000:
                self.requests = defaultdict(deque, {key: values for key, values in self.requests.items() if values and values[-1] > now - 60})
                self.last_sweep = now
                if len(self.requests) > 10_000:
                    return await reject("server_busy", 503)
            capability = path == '/api/paraphrase/capabilities' and scope['method'] == 'GET'
            if capability:
                recent = self.requests[(address, 'capabilities')]
                while recent and recent[0] <= now - 60:
                    recent.popleft()
                if len(recent) >= 60:
                    return await reject('rate_limited', 429)
                recent.append(now)
            if not capability and not (path in {"/api/queue", "/api/paraphrase/queue"} and scope["method"] in {"GET", "DELETE"}):
                recent = self.requests[address]
                while recent and recent[0] <= now - 60:
                    recent.popleft()
                if len(recent) >= 20:
                    return await reject("rate_limited", 429)
                recent.append(now)
                if scope['method'] == 'POST' and path in {'/api/paraphrase/queue', '/api/text/paraphrase'}:
                    nmt_recent = self.requests[(address, 'paraphrase')]
                    while nmt_recent and nmt_recent[0] <= now - 60:
                        nmt_recent.popleft()
                    if len(nmt_recent) >= 5:
                        return await reject('rate_limited', 429)
                    nmt_recent.append(now)
            try:
                if int(headers.get("content-length", "0")) > BODY_LIMIT:
                    return await reject("file_too_large", 413)
            except ValueError:
                return await reject("invalid_request", 400)
        received = 0
        async def limited_receive():
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if is_api and received > BODY_LIMIT:
                raise BodyLimit()
            return message
        try:
            await self.app(scope, limited_receive, secure_send)
        except BodyLimit:
            await reject("file_too_large", 413)


def _tools() -> dict:
    result = {}
    for name, args in {"exiftool": ["-ver"], "qpdf": ["--version"], "gs": ["--version"]}.items():
        executable = shutil.which(name)
        try:
            usable = bool(executable) and subprocess.run([executable, *args], capture_output=True, timeout=3).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            usable = False
        result[name] = usable
    return result


def create_app(*, jobs: Jobs | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        app.state.tools = await asyncio.to_thread(_tools)
        async def maintain_queue():
            while True:
                await asyncio.sleep(5)
                app.state.admission.sweep()
                cleanup_workdir()
        maintenance = asyncio.create_task(maintain_queue())
        try:
            yield
        finally:
            maintenance.cancel()
            await asyncio.gather(maintenance, return_exceptions=True)

    app = FastAPI(title="NoMark", version=__version__, docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    workdir = Path(os.environ.get("NOMARK_WORKDIR", str(Path(tempfile.gettempdir()) / "nomark-work")))
    if jobs is None:
        workdir.mkdir(parents=True, exist_ok=True, mode=0o700)
    def cleanup_workdir():
        if jobs is not None:
            return
        cleanup_stale_jobs(workdir)
    cleanup_workdir()
    app.state.jobs = jobs or Jobs(timeout=float(os.environ.get("NOMARK_TIMEOUT", "60")), temp_root=str(workdir))
    app.state.admission = Admission(capacity=app.state.jobs.concurrency)
    app.state.tools = {"exiftool": False, "qpdf": False, "gs": False}
    app.add_middleware(Guard)
    from nomark.paraphrase_routes import install
    install(app)

    def queue_token(request):
        value = request.headers.get("authorization", "")
        if not value.startswith("Bearer "):
            raise JobError("queue_expired", 410)
        return value[7:]

    async def admitted(request: Request):
        with app.state.admission.claim(request.headers.get("x-nomark-reservation")):
            yield

    async def run_job(request, mode, content, name=""):
        task = asyncio.create_task(app.state.jobs.run(mode, content, name))
        try:
            while not task.done():
                if await request.is_disconnected():
                    raise JobError("request_cancelled", 499)
                await asyncio.sleep(0.05)
            return {**await task, "processed_by": "server"}
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    @app.post("/api/queue")
    async def reserve():
        return app.state.admission.reserve()

    @app.get("/api/queue")
    async def queue_status(request: Request):
        return app.state.admission.status(queue_token(request))

    @app.delete("/api/queue")
    async def cancel_reservation(request: Request):
        app.state.admission.cancel(queue_token(request))
        return {"ok": True}

    @app.exception_handler(JobError)
    async def job_error(request, exc):
        return JSONResponse({"ok": False, "error": exc.code}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse({"ok": False, "error": "invalid_request"}, status_code=400)

    @app.get("/health")
    async def health():
        available = (ROOT / "watermarks-remover/service/scripts/text_unicode.py").is_file()
        return JSONResponse({"ok": available, "version": __version__, "engine_available": available, "pdf_ready": all(app.state.tools.values())}, status_code=200 if available else 503)

    @app.post("/api/text/process")
    async def text_process(request: Request, _slot=Depends(admitted)):
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            raise JobError("invalid_request", 415)
        try:
            async with asyncio.timeout(30):
                raw = await request.body()
            if len(raw) > TEXT_LIMIT * 12 + 100:
                raise JobError("text_too_large", 413)
            import json
            body = json.loads(raw)
        except (ValueError, UnicodeError, RecursionError):
            raise JobError("invalid_request", 400) from None
        except TimeoutError:
            raise JobError("upload_timeout", 408) from None
        text = body.get("text") if isinstance(body, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise JobError("empty_text", 400)
        if len(text) > TEXT_LIMIT:
            raise JobError("text_too_large", 413)
        try:
            content = text.encode("utf-8")
        except UnicodeError:
            raise JobError("invalid_encoding", 400) from None
        return await run_job(request, "text", content)

    @app.post("/api/file/process")
    async def file_process(request: Request, _slot=Depends(admitted)):
        try:
            async with asyncio.timeout(30), request.form(max_files=1, max_fields=0, max_part_size=FILE_LIMIT) as form:
                upload = form.get("file")
                if upload is None or not hasattr(upload, "filename") or len(form.multi_items()) != 1:
                    raise JobError("invalid_request", 400)
                name = upload.filename or ""
                if not name or len(name) > 240 or any(c in name for c in ("/", "\\", "\x00")) or any(ord(c) < 32 or ord(c) == 127 for c in name):
                    raise JobError("invalid_name", 400)
                if Path(name).suffix.lower() not in ALLOWED:
                    raise JobError("unsupported_format", 415)
                content = await upload.read(FILE_LIMIT + 1)
                if not content:
                    raise JobError("empty_file", 400)
                if len(content) > FILE_LIMIT:
                    raise JobError("file_too_large", 413)
        except JobError:
            raise
        except BodyLimit:
            raise
        except TimeoutError:
            raise JobError("upload_timeout", 408) from None
        except Exception:
            raise JobError("invalid_request", 400) from None
        return await run_job(request, "file", content, name)

    @app.get("/")
    @app.get("/id")
    @app.get("/en")
    async def index(request: Request):
        lang = "id" if request.url.path == "/id" else "en"
        return HTMLResponse(render_index(lang), headers={"Cache-Control": "no-cache", "Content-Language": lang})

    @app.get("/robots.txt", response_class=PlainTextResponse)
    async def robots():
        return f"User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /health\nDisallow: /static/index.html\nSitemap: {SITE}/sitemap.xml\n"

    @app.get("/sitemap.xml")
    async def sitemap_xml():
        return Response(sitemap(), media_type="application/xml")

    @app.get("/llms.txt", response_class=PlainTextResponse)
    async def llms():
        return llms_index()

    @app.get("/llms-full.txt", response_class=PlainTextResponse)
    async def full_context():
        return llms_full()

    @app.get("/favicon.ico")
    async def favicon():
        return FileResponse(ROOT / "static/brand/favicon.ico", media_type="image/vnd.microsoft.icon")

    @app.get("/site.webmanifest")
    async def manifest():
        return JSONResponse({"name": "NoMark", "short_name": "NoMark", "id": "/", "start_url": "/", "display": "browser", "background_color": "#f7f5ef", "theme_color": "#244d3c", "icons": [{"src": f"/static/brand/icon-{size}.png", "sizes": f"{size}x{size}", "type": "image/png", "purpose": "any"} for size in (192, 512)]}, media_type="application/manifest+json")

    @app.get("/id/privacy")
    @app.get("/en/privacy")
    @app.get("/id/terms")
    @app.get("/en/terms")
    async def policy(request: Request):
        _, lang, kind = request.url.path.split("/")
        return HTMLResponse(render_policy(lang, kind), headers={"Cache-Control": "no-cache", "Content-Language": lang})

    app.mount("/static", Assets(directory=ROOT / "static"), name="static")
    return app


app = create_app()
