"""Bounded real-model checks; execute only in the dedicated NMT staging container."""
import asyncio
import http.client
import json
from pathlib import Path
import time
import urllib.request

from nmt_service.runtime import Runtime


def model_pids():
    found = []
    for path in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            if b'spawn_main' in path.read_bytes(): found.append(int(path.parent.name))
        except OSError:
            pass
    return found


def request(text, language):
    started = time.monotonic()
    payload = json.dumps({'text': text, 'language': language}).encode()
    req = urllib.request.Request('http://127.0.0.1:8001/paraphrase', data=payload, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=85) as response:
        result = json.load(response)
    return {'language': language, 'characters': len(text), 'elapsed_ms': round((time.monotonic() - started) * 1000), 'status': result['status']}


async def real_timeout(text):
    runtime = Runtime('/models')
    async def connected(): return False
    try:
        started = time.monotonic()
        await runtime.process_text('Please review the result.', 'en', connected)
        cold_ms = round((time.monotonic() - started) * 1000)
        runtime.timeout = .05
        try:
            await runtime.process_text(text, 'en', connected)
        except TimeoutError:
            assert runtime.process is None
            return {'cold_ms': cold_ms, 'shortened_timeout_stopped_worker': True}
        raise AssertionError('Real inference unexpectedly completed inside test deadline')
    finally:
        runtime.stop()


def main():
    text = ('Please review the original meaning before using this result.\n' * 100)[:5000]
    original = set(model_pids())
    connection = http.client.HTTPConnection('127.0.0.1', 8001, timeout=5)
    connection.request('POST', '/paraphrase', body=json.dumps({'text': text, 'language': 'en'}), headers={'Content-Type': 'application/json'})
    time.sleep(.2)
    connection.close()
    deadline = time.monotonic() + 4
    while original.intersection(model_pids()) and time.monotonic() < deadline:
        time.sleep(.05)
    disconnected_stopped = not original.intersection(model_pids())
    assert original and disconnected_stopped
    measurements = [request(text, 'en'), request(('Tinjau makna asli sebelum menggunakan hasil ini.\n' * 120)[:5000], 'id')]
    timeout = asyncio.run(real_timeout(text))
    peak = Path('/sys/fs/cgroup/memory.peak')
    print(json.dumps({'disconnect_stopped_existing_worker': disconnected_stopped, 'maximum_input': measurements,
                      'real_timeout': timeout, 'container_memory_peak_bytes': int(peak.read_text()) if peak.exists() else None}))


if __name__ == '__main__':
    main()
