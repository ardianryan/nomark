from __future__ import annotations

import base64
import io
import mimetypes
import os
from pathlib import Path
import sys
import zipfile
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "watermarks-remover" / "service" / "scripts"))

from common import looks_binary
from container_meta import clean_container, detect_container_format, inspect_container
from text_unicode import clean_text, inspect_text
from nomark.media import IMAGE_EXTENSIONS, AV_EXTENSIONS, clean_media, validate_media

TEXT_LIMIT = 200_000
FILE_LIMIT = 20 * 1024 * 1024
EXTENSIONS = set(IMAGE_EXTENSIONS) | set(AV_EXTENSIONS) | {".txt", ".md", ".markdown", ".html", ".htm", ".pdf", ".docx", ".xlsx", ".pptx", ".odt", ".epub", ".svg", ".tex", ".latex"}
PACKAGES = {".docx": "word/document.xml", ".xlsx": "xl/workbook.xml", ".pptx": "ppt/presentation.xml", ".odt": "content.xml", ".epub": "META-INF/container.xml"}


class ProcessingError(Exception):
    def __init__(self, code: str, status: int = 422):
        self.code = code
        self.status = status
        super().__init__(code)


def validate_name(name: str) -> str:
    if not name or len(name) > 240 or any(c in name for c in ("/", "\\", "\x00")) or name in {".", ".."}:
        raise ProcessingError("invalid_name", 400)
    if any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise ProcessingError("invalid_name", 400)
    if Path(name).suffix.lower() not in EXTENSIONS:
        raise ProcessingError("unsupported_format", 415)
    return name


def _validate_document(data: bytes, suffix: str) -> None:
    if suffix in IMAGE_EXTENSIONS or suffix in AV_EXTENSIONS:
        try:
            validate_media(data, suffix)
        except Exception:
            raise ProcessingError("invalid_document") from None
        return
    # Encrypted OOXML is an OLE container, not a ZIP package.
    if data.startswith(bytes.fromhex("d0cf11e0a1b11ae1")):
        raise ProcessingError("encrypted_document")
    if suffix == ".pdf":
        from pypdf import PdfReader
        if not data.startswith(b"%PDF-"):
            raise ProcessingError("invalid_document")
        try:
            pdf = PdfReader(io.BytesIO(data), strict=True)
            if pdf.is_encrypted:
                raise ProcessingError("encrypted_document")
            if not pdf.pages:
                raise ProcessingError("invalid_document")
        except ProcessingError:
            raise
        except Exception:
            raise ProcessingError("invalid_document") from None
    elif suffix == '.svg':
        try:
            if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
                raise ProcessingError('invalid_document')
            element = ElementTree.fromstring(data)
            if element.tag.rsplit('}', 1)[-1] != 'svg':
                raise ProcessingError('invalid_document')
        except ProcessingError:
            raise
        except Exception:
            raise ProcessingError('invalid_document') from None
    elif suffix in PACKAGES:
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                entries = archive.infolist()
                if len(entries) > 2000 or sum(e.file_size for e in entries) > 128 * 1024 * 1024:
                    raise ProcessingError("archive_limit")
                if any(e.flag_bits & 1 for e in entries):
                    raise ProcessingError("encrypted_document")
                if any(e.file_size > 1024 * 1024 and e.file_size / max(e.compress_size, 1) > 200 for e in entries):
                    raise ProcessingError("archive_limit")
                if len(set(e.filename for e in entries)) != len(entries):
                    raise ProcessingError("invalid_document")
                if PACKAGES[suffix] not in archive.namelist():
                    raise ProcessingError("invalid_document")
                if "META-INF/encryption.xml" in archive.namelist():
                    raise ProcessingError("encrypted_document")
                if archive.testzip() is not None:
                    raise ProcessingError("invalid_document")
                for entry in entries:
                    if entry.filename.endswith((".xml", ".rels", ".opf")):
                        xml = archive.read(entry)
                        if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
                            raise ProcessingError("invalid_document")
                        ElementTree.fromstring(xml)
        except ProcessingError:
            raise
        except Exception:
            raise ProcessingError("invalid_document") from None


def _plain_report(report: dict) -> dict:
    return {k: v for k, v in report.items() if k != "path"}


def process_text(text: str, *, max_chars: int | None = TEXT_LIMIT) -> dict:
    if not text.strip():
        raise ProcessingError("empty_text", 400)
    if max_chars is not None and len(text) > max_chars:
        raise ProcessingError("text_too_large", 413)
    before = inspect_text(text).to_dict()
    cleaned, stats = clean_text(text)
    after = inspect_text(cleaned).to_dict()
    return {
        "kind": "text", "format": "text", "status": "cleaned" if cleaned != text else "unchanged",
        "cleaned_text": cleaned,
        "report": {"before": before, "after": after, "stats": stats, "actions": [], "warnings": []},
    }


def process_file(source: Path, name: str, directory: Path) -> dict:
    validate_name(name)
    data = source.read_bytes()
    if not data:
        raise ProcessingError("empty_file", 400)
    if len(data) > FILE_LIMIT:
        raise ProcessingError("file_too_large", 413)
    suffix = Path(name).suffix.lower()
    _validate_document(data, suffix)
    cleaned_name = f"{Path(name).stem}.cleaned{suffix}"
    if suffix == ".txt":
        if looks_binary(data):
            raise ProcessingError("invalid_document")
        try:
            text = data.decode("utf-8-sig")
        except UnicodeError:
            raise ProcessingError("invalid_encoding") from None
        result = process_text(text, max_chars=None)
        output = (b"\xef\xbb\xbf" if data.startswith(b"\xef\xbb\xbf") else b"") + result.pop("cleaned_text").encode("utf-8")
        result["kind"] = "file"
        result["format"] = "txt"
    elif suffix in IMAGE_EXTENSIONS or suffix in AV_EXTENSIONS:
        destination = directory / f"cleaned{suffix}"
        before, after, actions, partial = clean_media(source, destination, data, suffix)
        output = destination.read_bytes()
        try:
            validate_media(output, suffix)
        except Exception:
            raise ProcessingError('processing_failed') from None
        result = {
            "kind": "file", "format": after['format'],
            "status": "partial" if partial else "cleaned" if output != data else "unchanged",
            "report": {"before": _plain_report(before), "after": _plain_report(after), "actions": actions,
                       "warnings": (["residual_metadata"] if partial else []) + (["image_metadata_notice"] if suffix in IMAGE_EXTENSIONS else [])},
        }
    else:
        if suffix in {".md", ".markdown", ".html", ".htm", ".tex", ".latex"}:
            if looks_binary(data):
                raise ProcessingError("invalid_document")
            try:
                data.decode("utf-8-sig")
            except UnicodeError:
                raise ProcessingError("invalid_encoding") from None
        source_with_ext = directory / f"input{suffix}"
        source_with_ext.write_bytes(data)
        fmt = detect_container_format(source_with_ext, data)
        before = _plain_report(inspect_container(source_with_ext).to_dict())
        destination = directory / f"cleaned{suffix}"
        report = clean_container(source_with_ext, destination, fmt=fmt, also_layer_a_text=True)
        output = destination.read_bytes()
        # clean_container already inspects the output; avoid a second native PDF scan.
        after = {"format": fmt, "has_c2pa": report.get("still_has_c2pa", False), "has_ai_metadata": report.get("still_has_ai_metadata", False), "findings": report.get("post_findings", []), "notes": []}
        meta = report.get("meta", {})
        partial = bool(report.get("still_has_c2pa") or report.get("still_has_ai_metadata") or meta.get("degraded"))
        warnings = ["residual_metadata"] if report.get("still_has_c2pa") or report.get("still_has_ai_metadata") else []
        if meta.get("degraded"):
            warnings.append("limited_pdf_tools")
        result = {
            "kind": "file", "format": fmt,
            "status": "partial" if partial else "cleaned" if output != data else "unchanged",
            "report": {"before": before, "after": after, "actions": report.get("actions", []), "warnings": warnings},
        }
    if len(output) > FILE_LIMIT * 2:
        raise ProcessingError("output_too_large", 413)
    result.update({"name": name, "cleaned_name": cleaned_name, "mime": mimetypes.guess_type(cleaned_name)[0] or "application/octet-stream", "cleaned_base64": base64.b64encode(output).decode("ascii"), "bytes_in": len(data), "bytes_out": len(output)})
    # Public reports must not expose local paths emitted by upstream tools.
    return _scrub_paths(result, str(directory))


def _scrub_paths(value, directory: str):
    if isinstance(value, str):
        return value.replace(directory, "[temporary]")
    if isinstance(value, dict):
        return {k: _scrub_paths(v, directory) for k, v in value.items() if k not in {"path", "input", "output"}}
    if isinstance(value, list):
        return [_scrub_paths(v, directory) for v in value]
    return value
