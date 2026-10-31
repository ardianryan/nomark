"""Bounded client for the optional, operator-configured NMT service."""
import asyncio
import json
import os

import httpx

from nomark.jobs import JobError

LIMIT = 5000
BODY_LIMIT = 65536


def validate_edits(value, source, output):
    if not isinstance(value, list) or len(value) > 256:
        return []
    cleaned, ids = [], set()
    input_end = output_end = 0
    for item in value:
        if not isinstance(item, dict):
            return []
        keys = ('input_start', 'input_end', 'output_start', 'output_end')
        if any(type(item.get(key)) is not int for key in keys):
            return []
        a, b, c, d = (item[key] for key in keys)
        identifier = item.get('id')
        alternatives = item.get('alternatives')
        if (not isinstance(identifier, str) or not 0 < len(identifier) <= 64 or identifier in ids
                or not input_end <= a < b <= len(source) or not output_end <= c < d <= len(output)
                or item.get('before') != source[a:b] or item.get('after') != output[c:d]
                or len(source[a:b]) > 128 or len(output[c:d]) > 128
                or not isinstance(alternatives, list) or len(alternatives) > 3):
            return []
        for phrase in alternatives:
            if not isinstance(phrase, str) or not phrase.strip() or len(phrase) > 128:
                return []
            try:
                phrase.encode('utf-8')
            except UnicodeError:
                return []
        if len(set(alternatives)) != len(alternatives):
            return []
        cleaned.append({key: item[key] for key in ('id', *keys, 'before', 'after', 'alternatives')})
        ids.add(identifier)
        input_end, output_end = b, d
    return cleaned


class NMTClient:
    def __init__(self, url=None, transport=None):
        self.url = (url if url is not None else os.environ.get('NOMARK_NMT_URL', '')).rstrip('/')
        self.transport = transport

    async def request(self, path, payload=None):
        try:
            async with asyncio.timeout(85):
                return await self._request(path, payload)
        except TimeoutError:
            raise JobError('paraphrase_timeout', 504) from None

    async def _request(self, path, payload=None):
        if not self.url:
            raise JobError('paraphrase_unavailable', 503)
        try:
            async with httpx.AsyncClient(timeout=85, trust_env=False, follow_redirects=False,
                                         transport=self.transport) as client:
                async with client.stream('GET' if payload is None else 'POST', self.url + path, json=payload) as response:
                    raw = bytearray()
                    async for chunk in response.aiter_bytes():
                        raw.extend(chunk)
                        if len(raw) > 1024 * 1024:
                            raise JobError('paraphrase_failed', 502)
                    if response.status_code != 200:
                        mapping = {503: ('paraphrase_unavailable', 503), 504: ('paraphrase_timeout', 504)}
                        code, status = mapping.get(response.status_code, ('paraphrase_failed', 502))
                        raise JobError(code, status)
            result = json.loads(raw)
        except httpx.TimeoutException:
            raise JobError('paraphrase_timeout', 504) from None
        except httpx.HTTPError:
            raise JobError('paraphrase_unavailable', 503) from None
        except (ValueError, UnicodeError, RecursionError):
            raise JobError('paraphrase_failed', 502) from None
        if not isinstance(result, dict) or result.get('ok') is not True:
            raise JobError('paraphrase_failed', 502)
        return result

    async def wait_idle(self):
        try:
            async with asyncio.timeout(3):
                while (await self.request('/idle')).get('idle') is not True:
                    await asyncio.sleep(.025)
            return True
        except (JobError, TimeoutError):
            return False

    async def available(self):
        if not self.url:
            return False
        try:
            async with asyncio.timeout(3):
                return (await self.request('/health')).get('ready') is True
        except (JobError, TimeoutError):
            return False

    async def process(self, text, language):
        result = await self.request('/paraphrase', {'text': text, 'language': language})
        output = result.get('paraphrased_text')
        warnings = result.get('warnings')
        if (not isinstance(output, str) or not output.strip() or len(output) > 50000
                or result.get('language') != language
                or result.get('status') not in {'paraphrased', 'unchanged', 'partial'}
                or not isinstance(warnings, list) or len(warnings) > 10
                or any(value not in {'review_required', 'segments_preserved'} for value in warnings)):
            raise JobError('paraphrase_failed', 502)
        try:
            output.encode('utf-8')
        except UnicodeError:
            raise JobError('paraphrase_failed', 502) from None
        return {'ok': True, 'paraphrased_text': output, 'language': language,
                'edits': validate_edits(result.get('edits', []), text, output),
                'status': result['status'], 'warnings': warnings, 'processed_by': 'server'}
