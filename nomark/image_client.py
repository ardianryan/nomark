"""Strict, bounded transport for the optional private media service."""
import asyncio
import base64
import binascii
import json
import os
from pathlib import Path
import re

import httpx
from nomark.jobs import JobError

INPUT_LIMIT = 20 * 1024 * 1024
OUTPUT_LIMIT = 40 * 1024 * 1024
RESPONSE_LIMIT = 56 * 1024 * 1024
ERRORS = {'invalid_document', 'image_dimensions', 'image_animation', 'image_color_mode',
          'empty_file', 'file_too_large', 'unsupported_format', 'output_too_large',
          'media_timeout', 'media_unavailable', 'upload_timeout', 'request_cancelled', 'processing_failed'}


def validate_name(name):
    if (not isinstance(name, str) or not 0 < len(name) <= 240 or
            any(c in name for c in ('/', '\\')) or any(ord(c) < 32 or ord(c) == 127 for c in name)):
        raise JobError('invalid_name', 400)
    if Path(name).suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp'}:
        raise JobError('unsupported_format', 415)
    return name


class MediaClient:
    def __init__(self, url=None, transport=None):
        self.url = (url if url is not None else os.environ.get('NOMARK_MEDIA_URL', '')).rstrip('/')
        self.transport = transport

    async def request(self, method, path, **kwargs):
        if not self.url: raise JobError('media_unavailable', 503)
        try:
            async with asyncio.timeout(75), httpx.AsyncClient(timeout=75, trust_env=False, follow_redirects=False, transport=self.transport) as client:
                async with client.stream(method, self.url + path, **kwargs) as response:
                    if response.status_code != 200:
                        # Only bounded, known service errors cross this boundary.
                        raw = bytearray()
                        async for chunk in response.aiter_bytes():
                            raw.extend(chunk)
                            if len(raw) > 4096: raise JobError('media_failed', 502)
                        try: code = json.loads(raw).get('error')
                        except (ValueError, AttributeError, RecursionError): code = None
                        if code in ERRORS and response.status_code in {400, 408, 413, 415, 422, 499, 503, 504}:
                            raise JobError(code, response.status_code)
                        raise JobError('media_failed', 502)
                    raw = bytearray()
                    limit = RESPONSE_LIMIT if path == '/process' else 4096
                    async for chunk in response.aiter_bytes():
                        raw.extend(chunk)
                        if len(raw) > limit: raise JobError('media_failed', 502)
            result = json.loads(raw)
            if not isinstance(result, dict) or result.get('ok') is not True:
                raise JobError('media_failed', 502)
            return result
        except (httpx.TimeoutException, TimeoutError):
            raise JobError('media_timeout', 504) from None
        except httpx.HTTPError:
            raise JobError('media_unavailable', 503) from None
        except (ValueError, UnicodeError, RecursionError):
            raise JobError('media_failed', 502) from None

    async def available(self):
        if not self.url: return False
        try:
            async with asyncio.timeout(3): return (await self.request('GET', '/health')).get('ready') is True
        except (JobError, TimeoutError): return False

    async def wait_idle(self):
        try:
            async with asyncio.timeout(3):
                while (await self.request('GET', '/idle')).get('idle') is not True:
                    await asyncio.sleep(.025)
            return True
        except (JobError, TimeoutError): return False

    async def stop(self, job_id):
        try:
            async with asyncio.timeout(5):
                stopped = (await self.request('DELETE', '/jobs/' + job_id)).get('stopped') is True
                return stopped and await self.wait_idle()
        except (JobError, TimeoutError): return False

    async def process(self, content, name, job_id):
        result = await self.request('POST', '/process', files={'file': (name, content, 'application/octet-stream')}, headers={'X-NoMark-Job': job_id})
        try:
            encoded = result['cleaned_base64']
            if not isinstance(encoded, str) or len(encoded) > 4 * ((OUTPUT_LIMIT + 2) // 3): raise ValueError
            decoded = base64.b64decode(encoded, validate=True)
            if not 33 <= len(decoded) <= OUTPUT_LIMIT or decoded[:8] != b'\x89PNG\r\n\x1a\n' or decoded[12:16] != b'IHDR': raise ValueError
            w, h = int.from_bytes(decoded[16:20], 'big'), int.from_bytes(decoded[20:24], 'big')
            if not 0 < w <= 8192 or not 0 < h <= 8192 or w * h > 8_000_000 or decoded[24:26] != b'\x08\x06': raise ValueError
            if type(result['width']) is not int or type(result['height']) is not int or (w, h) != (result['width'], result['height']): raise ValueError
            if type(result['bytes_out']) is not int or result['bytes_out'] != len(decoded) or type(result['bytes_in']) is not int or result['bytes_in'] != len(content): raise ValueError
            if type(result['elapsed_ms']) is not int or not 0 <= result['elapsed_ms'] <= 75_000: raise ValueError
            visual = result['visual_status']
            if visual not in {'no_watermark', 'cleaned', 'partial', 'unvalidated'}: raise ValueError
            marks = result['marks']
            if not isinstance(marks, list) or len(marks) > 64: raise ValueError
            clean_marks = []
            for mark in marks:
                if (not isinstance(mark, dict) or not isinstance(mark.get('key'), str) or not re.fullmatch('[a-z0-9_-]{1,64}', mark['key'])
                        or not isinstance(mark.get('label'), str) or not 0 < len(mark['label']) <= 120
                        or any(ord(c) < 32 for c in mark['label']) or mark.get('status') not in {'cleaned', 'partial', 'unvalidated'}): raise ValueError
                clean_marks.append({k: mark[k] for k in ('key', 'label', 'status')})
            if visual == 'no_watermark' and clean_marks or visual != 'no_watermark' and not clean_marks: raise ValueError
            expected = 'partial' if any(m['status'] == 'partial' for m in clean_marks) else 'unvalidated' if any(m['status'] == 'unvalidated' for m in clean_marks) else 'cleaned' if clean_marks else 'no_watermark'
            if visual != expected or type(result['metadata_removed']) is not bool or result.get('normalized') is not True: raise ValueError
        except (KeyError, TypeError, ValueError, binascii.Error, OverflowError):
            raise JobError('media_failed', 502) from None
        status = 'partial' if visual in {'partial', 'unvalidated'} else 'cleaned' if clean_marks or result['metadata_removed'] else 'unchanged'
        return {'ok': True, 'kind': 'image', 'format': 'png', 'mime': 'image/png', 'name': name,
                'cleaned_name': Path(name).stem + '.cleaned.png', 'status': status, 'visual_status': visual,
                'width': w, 'height': h, 'bytes_in': len(content), 'bytes_out': len(decoded),
                'cleaned_base64': encoded, 'elapsed_ms': result['elapsed_ms'], 'processed_by': 'server',
                'report': {'marks': clean_marks, 'metadata_removed': result['metadata_removed'], 'normalized': True,
                           'warnings': ['image_review']}}
