import asyncio
import json
import os
from pathlib import Path
import sys
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nmt_service.runtime import Runtime


def synthetic_worker(connection, root):
    os.setsid()
    connection.send_bytes(b'{"ready":true}')
    while True:
        data = json.loads(connection.recv_bytes())
        if data['text'] == 'wait': time.sleep(30)
        connection.send_bytes(json.dumps({'ok': True, 'pid': os.getpid()}).encode())


async def connected(): return False


def test_warm_reuse_and_idle_eviction():
    runtime = Runtime('/unused', idle=0, target=synthetic_worker)
    async def scenario():
        first = await runtime.process_text('one', 'id', connected)
        second = await runtime.process_text('two', 'en', connected)
        assert first['pid'] == second['pid']
        runtime.sweep()
        assert runtime.process is None
    asyncio.run(scenario())


@pytest.mark.parametrize('mode', ['timeout', 'cancel', 'disconnect'])
def test_hard_stop_and_recovery(mode):
    runtime = Runtime('/unused', timeout=.5, target=synthetic_worker)
    async def scenario():
        await runtime.process_text('ready', 'en', connected)
        async def disconnected(): return mode == 'disconnect'
        task = asyncio.create_task(runtime.process_text('wait', 'id', disconnected))
        if mode == 'cancel':
            await asyncio.sleep(.1)
            task.cancel()
        with pytest.raises(TimeoutError if mode == 'timeout' else asyncio.CancelledError): await task
        assert runtime.process is None
        runtime.timeout = 5
        assert (await runtime.process_text('recover', 'en', connected))['ok']
        runtime.stop()
    asyncio.run(scenario())


def test_model_checksums_reject_corruption_and_traversal(tmp_path):
    import hashlib
    files = {}
    for pair in ('en-id', 'id-en'):
        for name in ('model.bin', 'tokenizer/tokenizer_config.json', 'tokenizer/source.spm', 'tokenizer/target.spm', 'tokenizer/vocab.json'):
            relative = f'{pair}/{name}'
            path = tmp_path / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'synthetic')
            files[relative] = hashlib.sha256(b'synthetic').hexdigest()
    manifest = tmp_path / 'checksums.json'
    manifest.write_text(json.dumps(files))
    assert Runtime(str(tmp_path)).ready()
    (tmp_path / 'en-id/model.bin').write_bytes(b'corrupted')
    assert not Runtime(str(tmp_path)).ready()
    (tmp_path / 'en-id/model.bin').write_bytes(b'synthetic')
    files['../outside'] = 'unused'
    manifest.write_text(json.dumps(files))
    assert not Runtime(str(tmp_path)).ready()
