import asyncio
from pathlib import Path
import time
import pytest
from media_service.pipeline import ImageError
from media_service.runtime import Runtime


def slow_worker(directory,name):
    import os
    os.setsid()
    time.sleep(20)


@pytest.mark.parametrize('mode', ['timeout','disconnect','cancel'])
def test_runtime_kills_worker_and_cleans_directory(tmp_path,mode):
    async def scenario():
        runtime=Runtime(str(tmp_path),timeout=.25 if mode=='timeout' else 10,target=slow_worker)
        started=time.monotonic()
        async def disconnected(): return mode=='disconnect' and time.monotonic()-started>.2
        task=asyncio.create_task(runtime.process_image(b'data','test.png','a'*32,disconnected))
        if mode=='cancel':
            await asyncio.sleep(.2); assert runtime.cancel('a'*32)
        with pytest.raises(ImageError): await task
        assert runtime.process is None and not runtime.lock.locked()
        assert list(tmp_path.iterdir())==[]
    asyncio.run(scenario())


def test_cancel_before_post_prevents_late_inference(tmp_path):
    async def scenario():
        runtime=Runtime(str(tmp_path));assert runtime.cancel('b'*32)
        with pytest.raises(ImageError) as e: await runtime.process_image(b'data','test.png','b'*32,lambda:None)
        assert e.value.code=='request_cancelled'
        assert list(tmp_path.iterdir())==[]
    asyncio.run(scenario())


def test_cancellation_tombstone_exhaustion_rejects_late_posts(tmp_path):
    async def scenario():
        runtime=Runtime(str(tmp_path))
        for i in range(128): runtime.cancel(f'{i:032x}')
        with pytest.raises(RuntimeError): runtime.cancel('f'*32)
        with pytest.raises(ImageError) as caught:
            await runtime.process_image(b'data','test.png','f'*32,lambda:None)
        assert caught.value.code=='media_unavailable'
    asyncio.run(scenario())


@pytest.mark.skipif(__import__('sys').platform!='linux',reason='Linux seccomp worker enforcement')
def test_native_socket_creation_is_blocked_in_a_subprocess():
    import subprocess,sys
    code='from media_service.sandbox import deny_network; import socket; deny_network(); socket.socket()'
    result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True)
    assert result.returncode!=0 and 'PermissionError' in result.stderr


def crash_worker(directory,name):
    import os
    os.setsid();os._exit(17)


def test_worker_crash_cleans_files_and_real_worker_recovers(tmp_path):
    import io
    from PIL import Image
    from media_service.runtime import worker
    async def scenario():
        image=io.BytesIO();Image.new('RGBA',(96,80),(10,20,30,170)).save(image,'PNG')
        runtime=Runtime(str(tmp_path),target=crash_worker)
        async def connected():return False
        with pytest.raises(ImageError):await runtime.process_image(image.getvalue(),'test.png','c'*32,connected)
        assert runtime.process is None and list(tmp_path.iterdir())==[]
        runtime.target=worker
        assert (await runtime.process_image(image.getvalue(),'test.png','d'*32,connected))['ok']
        assert runtime.process is None and list(tmp_path.iterdir())==[]
    asyncio.run(scenario())
