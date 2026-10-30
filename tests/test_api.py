import base64
import io
from pathlib import Path
import zipfile

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter

from nomark.app import create_app
from nomark.engine import process_text

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client():
    with TestClient(create_app()) as test_client:
        yield test_client


def package(entries):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return output.getvalue()


def docx():
    return package({
        "[Content_Types].xml": '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>',
        "word/document.xml": '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Halo\u200bdunia</w:t></w:r></w:p></w:body></w:document>',
        "docProps/core.xml": '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:creator>ChatGPT</dc:creator></cp:coreProperties>',
    })


def odt():
    return package({
        "mimetype": "application/vnd.oasis.opendocument.text",
        "META-INF/manifest.xml": '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"><manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.text"/></manifest:manifest>',
        "content.xml": '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"><office:body><office:text><text:p>Halo\u200bdunia</text:p></office:text></office:body></office:document-content>',
        "meta.xml": '<office:document-meta xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0"><office:meta><meta:generator>ChatGPT</meta:generator></office:meta></office:document-meta>',
    })


def epub():
    return package({
        "mimetype": "application/epub+zip",
        "META-INF/container.xml": '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0"><rootfiles><rootfile full-path="content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>',
        "content.opf": '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Test</dc:title><dc:identifier id="id">urn:uuid:test</dc:identifier><meta property="generator">ChatGPT</meta></metadata><manifest><item id="page" href="page.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="page"/></spine></package>',
        "page.xhtml": '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Test</title></head><body><p>Halo\u200bdunia</p></body></html>',
    })


def pdf(encrypted=False):
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_metadata({"/Author": "ChatGPT", "/Title": "Test"})
    if encrypted:
        writer.encrypt("secret")
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.mark.parametrize("text", ["Halo dunia!", "café Ελληνικά العربية", "👩‍💻 🇮🇩 ❤️‍🔥", "السعر \u2066123 USD\u2069\u200f"])
def test_legitimate_content_is_preserved(text):
    result = process_text(text)
    assert result["cleaned_text"] == text
    assert result["status"] == "unchanged"


def test_text_api_removes_hidden_unicode_without_rewriting(client):
    response = client.post("/api/text/process", json={"text": "Halo\u200bdunia\u00a0👩‍💻"})
    assert response.status_code == 200
    result = response.json()
    assert result["cleaned_text"] == "Halodunia 👩‍💻"
    assert result["status"] == "cleaned"
    assert result["report"]["stats"]["removed_count"] == 1
    assert result["report"]["stats"]["replaced_count"] == 1
    assert response.headers["cache-control"] == "no-store"
    assert "'unsafe-eval'" not in response.headers["content-security-policy"]
    assert "'wasm-unsafe-eval'" in response.headers["content-security-policy"]


@pytest.mark.parametrize("body,code", [({"text": ""}, "empty_text"), ({"text": " "}, "empty_text"), ({"text": 1}, "empty_text"), ({"text": "a" * 200001}, "text_too_large"), ({"text": "\ud800"}, "invalid_encoding")])
def test_invalid_text(client, body, code):
    response = client.post("/api/text/process", content=__import__('json').dumps(body), headers={"Content-Type": "application/json"})
    assert response.status_code in {400, 413}
    assert response.json()["error"] == code


@pytest.mark.parametrize("extension,content", [
    ("txt", "Halo\u200bdunia".encode()),
    ("md", "---\nai_generated: true\n---\nHalo\u200bdunia".encode()),
    ("markdown", "Halo\u200bdunia".encode()),
    ("html", '<html><head><meta name="generator" content="ChatGPT"></head><body>Halo\u200bdunia</body></html>'.encode()),
    ("htm", '<html><body>Halo\u200bdunia</body></html>'.encode()),
    ("docx", docx()), ("odt", odt()), ("epub", epub()), ("pdf", pdf()),
    ("xlsx", (ROOT / "watermarks-remover/tests/fixtures/sample_ai.xlsx").read_bytes()),
    ("pptx", (ROOT / "watermarks-remover/tests/fixtures/sample_ai.pptx").read_bytes()),
])
def test_all_document_formats(client, extension, content):
    response = client.post("/api/file/process", files={"file": (f"draft.{extension}", content)})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["name"] == f"draft.{extension}"
    assert result["cleaned_name"] == f"draft.cleaned.{extension}"
    assert result["status"] in {"cleaned", "unchanged", "partial"}
    cleaned = base64.b64decode(result["cleaned_base64"])
    assert cleaned
    if extension == "pdf":
        assert len(PdfReader(io.BytesIO(cleaned)).pages) == 1
        if not client.get("/health").json()["pdf_ready"]:
            assert result["status"] == "partial"
            assert "limited_pdf_tools" in result["report"]["warnings"]
    elif extension in {"docx", "odt", "epub", "xlsx", "pptx"}:
        with zipfile.ZipFile(io.BytesIO(cleaned)) as archive:
            assert archive.testzip() is None
            contents = b"".join(archive.read(n) for n in archive.namelist() if n.endswith((".xml", ".xhtml")))
            assert b"\xe2\x80\x8b" not in contents
    else:
        assert "\u200b" not in cleaned.decode()
    assert "/private/" not in str(result["report"])
    assert "/tmp/nomark" not in str(result["report"])


@pytest.mark.parametrize("name,data,error", [
    ("photo.png", b"\x89PNG", "unsupported_format"),
    ("video.mp4", b"test", "unsupported_format"),
    ("../draft.txt", b"test", "invalid_name"),
    ("draft\\test.txt", b"test", "invalid_name"),
    ("blank.txt", b"", "empty_file"),
    ("broken.docx", b"not a zip", "invalid_document"),
    ("broken.pdf", b"%PDF-broken", "invalid_document"),
    ("renamed.txt", b"%PDF-1.4\n", "invalid_document"),
    ("renamed.md", b"\x89PNG\r\n\x1a\n", "invalid_document"),
    ("latin.txt", b"caf\xe9", "invalid_encoding"),
    ("encrypted.pdf", pdf(True), "encrypted_document"),
    ("encrypted.docx", bytes.fromhex("d0cf11e0a1b11ae1") + b"data", "encrypted_document"),
    ("expanded.docx", package({"word/document.xml": b"a" * (2 * 1024 * 1024)}), "archive_limit"),
])
def test_rejects_unsafe_uploads(client, name, data, error):
    response = client.post("/api/file/process", files={"file": (name, data)})
    assert response.status_code in {400, 413, 415, 422}, response.text
    assert response.json()["error"] == error


def test_file_size_enforced_before_processing(client):
    response = client.post("/api/file/process", files={"file": ("large.txt", b"a" * (20 * 1024 * 1024 + 1))})
    assert response.status_code == 413
    assert response.json()["error"] == "file_too_large"


def test_rejects_multiple_files_per_server_request(client):
    response = client.post("/api/file/process", files=[("file", ("one.txt", b"hello")), ("file", ("two.txt", b"world"))])
    assert response.status_code == 400


def test_bom_preserved(client):
    response = client.post("/api/file/process", files={"file": ("bom.txt", b"\xef\xbb\xbfhello\xe2\x80\x8b")})
    assert base64.b64decode(response.json()["cleaned_base64"]) == b"\xef\xbb\xbfhello"


def test_uploaded_text_uses_file_limit_instead_of_paste_limit(client):
    content = b"a" * 200001
    response = client.post("/api/file/process", files={"file": ("long.txt", content)})
    assert response.status_code == 200
    assert base64.b64decode(response.json()["cleaned_base64"]) == content


def test_origin_rate_limit_and_health(client):
    response = client.post("/api/text/process", headers={"Origin": "https://other.example"}, json={"text": "hello"})
    assert response.status_code == 403
    for _ in range(20):
        client.post("/api/text/process", json={"text": ""})
    response = client.post("/api/text/process", json={"text": ""})
    assert response.status_code == 429
    assert client.get("/health").status_code == 200


def test_static_html_and_licenses_are_served_without_auth(client):
    assert client.get("/").status_code == 200
    assert "watermarks-remover" in client.get("/static/notices.txt").text
    assert client.get("/static/vendor/alpine-csp.min.js").status_code == 200
    assert client.get("/health").json()["engine_available"]


def test_streaming_body_limit_does_not_trust_content_length(client, monkeypatch):
    import nomark.app
    monkeypatch.setattr(nomark.app, "BODY_LIMIT", 1024)
    def chunks():
        yield b'{"text":"'
        yield b"a" * 2048
        yield b'"}'
    response = client.post("/api/text/process", content=chunks(), headers={"Content-Type": "application/json"})
    assert response.status_code == 413
    assert response.json()["error"] == "file_too_large"


def test_html_is_returned_as_data_and_cannot_execute(client):
    content = b'<html><body><script>window.uploadExecuted=true</script>Hello</body></html>'
    response = client.post("/api/file/process", files={"file": ("page.html", content)})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert "cleaned_base64" in response.json()


@pytest.mark.parametrize("language,kind,title", [("id", "privacy", "Kebijakan privasi"), ("en", "privacy", "Privacy policy"), ("id", "terms", "Ketentuan layanan"), ("en", "terms", "Terms of service")])
def test_public_policies_match_processing_routes(client, language, kind, title):
    response = client.get(f"/{language}/{kind}")
    assert response.status_code == 200
    assert f'lang="{language}"' in response.text
    assert title in response.text
    assert "me@ardianryan.com" in response.text
    assert "Alat pribadi" not in response.text
    assert response.headers["cache-control"] == "no-cache"


def test_queue_admission_before_file_body_parsing(client, monkeypatch):
    tickets = [client.post("/api/queue").json() for _ in range(3)]
    assert [ticket["state"] for ticket in tickets] == ["ready", "ready", "waiting"]
    from starlette.requests import Request
    def unexpected_form(*args, **kwargs):
        raise AssertionError("Upload body must not be parsed without capacity")
    monkeypatch.setattr(Request, "form", unexpected_form)
    response = client.post("/api/file/process", files={"file": ("example.pdf", b"contents")})
    assert response.status_code == 503
    assert response.json()["error"] == "server_busy"
    cancelled = client.delete("/api/queue", headers={"Authorization": f"Bearer {tickets[0]['token']}"})
    assert cancelled.status_code == 200
    status = client.get("/api/queue", headers={"Authorization": f"Bearer {tickets[2]['token']}"})
    assert status.json()["state"] == "ready"


def test_queue_ticket_used_once_and_released_on_failure(client):
    ticket = client.post("/api/queue").json()
    response = client.post("/api/file/process", headers={"X-NoMark-Reservation": ticket["token"]}, files={"file": ("broken.pdf", b"broken")})
    assert response.status_code == 422
    assert client.app.state.admission.active == 0
    assert client.get("/api/queue", headers={"Authorization": f"Bearer {ticket['token']}"}).status_code == 410
    response = client.post("/api/file/process", headers={"X-NoMark-Reservation": ticket["token"]}, files={"file": ("broken.pdf", b"broken")})
    assert response.status_code == 410


def test_only_versioned_engine_assets_are_cacheable(client):
    response = client.get("/static/vendor/pyodide/314.0.7/pyodide.mjs")
    assert "immutable" in response.headers["cache-control"]
    assert client.get("/static/engine-manifest.json").headers["cache-control"] == "no-cache"
    assert client.post("/api/queue").headers["cache-control"] == "no-store"


def test_precompressed_assets_preserve_mime_and_negotiate_encoding(client):
    path = "/static/vendor/pyodide/314.0.7/pyodide.asm.wasm"
    compressed = client.get(path, headers={"Accept-Encoding": "gzip"})
    assert compressed.status_code == 200
    assert compressed.headers["content-encoding"] == "gzip"
    assert compressed.headers["content-type"] == "application/wasm"
    assert compressed.content[:4] == b"\x00asm"
    plain = client.get(path, headers={"Accept-Encoding": "gzip;q=0"})
    assert "content-encoding" not in plain.headers
    assert plain.content == compressed.content
    assert len(compressed.content) > int(compressed.headers["content-length"]) * 2
    assert plain.headers["vary"] == "Accept-Encoding"


def test_abandoned_work_directories_are_cleaned_without_touching_recent_jobs(tmp_path, monkeypatch):
    import os
    import time
    workdir = tmp_path / "work"
    old = workdir / "nomark-old"
    recent = workdir / "nomark-recent"
    unrelated = workdir / "other"
    for directory in (old, recent, unrelated):
        directory.mkdir(parents=True)
    os.utime(old, (time.time() - 400, time.time() - 400))
    monkeypatch.setenv("NOMARK_WORKDIR", str(workdir))
    create_app()
    assert not old.exists()
    assert recent.exists()
    assert unrelated.exists()
