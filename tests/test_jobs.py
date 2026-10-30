import asyncio
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import shutil

import pytest

import nomark.jobs as jobs_module
from nomark.jobs import JobError, Jobs
from tests.job_fixtures import paused_attachment_worker, resource_probe_worker, slow_worker


def is_running(pid):
    if sys.platform == 'linux':
        try:
            state = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0]
            return state != 'Z'
        except FileNotFoundError:
            return False
    result = subprocess.run(["ps", "-p", str(pid), "-o", "stat="], capture_output=True, text=True)
    return result.returncode == 0 and "Z" not in result.stdout


def test_success_and_failure_remove_temporary_files(tmp_path):
    jobs = Jobs(temp_root=str(tmp_path))
    result = asyncio.run(jobs.run("text", "Hallo\u200b".encode()))
    assert result["cleaned_text"] == "Hallo"
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(JobError):
        asyncio.run(jobs.run("file", b"broken", "sample.docx"))
    assert list(tmp_path.iterdir()) == []
    assert jobs.active == 0


def test_timeout_kills_descendants_and_removes_temp_files(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs_module, "worker", slow_worker)
    job_root = tmp_path / "jobs"
    job_root.mkdir()
    child_pid = tmp_path / "child.pid"
    jobs = Jobs(timeout=2, temp_root=str(job_root))
    with pytest.raises(JobError) as exc:
        asyncio.run(jobs.run("text", b"hello", str(child_pid)))
    assert exc.value.code == "processing_timeout"
    assert child_pid.exists()
    assert not is_running(int(child_pid.read_text()))
    assert list(job_root.iterdir()) == []
    assert jobs.active == 0


def test_busy_and_cancellation_release_capacity(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs_module, "worker", slow_worker)
    job_root = tmp_path / "jobs"
    job_root.mkdir()
    pid_file = tmp_path / "child.pid"
    jobs = Jobs(timeout=10, concurrency=1, temp_root=str(job_root))
    async def scenario():
        task = asyncio.create_task(jobs.run("text", b"hello", str(pid_file)))
        for _ in range(100):
            if pid_file.exists():
                break
            await asyncio.sleep(0.05)
        with pytest.raises(JobError) as exc:
            await jobs.run("text", b"second")
        assert exc.value.code == "server_busy"
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(scenario())
    assert not is_running(int(pid_file.read_text()))
    assert jobs.active == 0
    assert list(job_root.iterdir()) == []


@pytest.mark.skipif(sys.platform != 'linux', reason='Worker resource limits are Linux-specific')
def test_worker_kernel_limits_reject_excess_memory_and_file_size(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs_module, 'worker', resource_probe_worker)
    jobs = Jobs(temp_root=str(tmp_path))
    result = asyncio.run(jobs.run('text', b'probe'))
    assert result['memory_blocked'] is True
    assert result['file_blocked'] is True
    assert result['address_space'] == [768 * 1024 * 1024] * 2
    assert result['file_size'] == [256 * 1024 * 1024] * 2
    assert jobs.active == 0
    assert list(tmp_path.iterdir()) == []


@pytest.mark.skipif(shutil.which('qpdf') is None, reason='Real PDF extraction requires qpdf')
@pytest.mark.parametrize('cancel', [False, True], ids=['timeout', 'cancellation'])
def test_real_pdf_attachment_staging_is_owned_and_removed(tmp_path, monkeypatch, cancel):
    from pypdf import PdfWriter

    source = io.BytesIO()
    pdf = PdfWriter()
    pdf.add_blank_page(width=72, height=72)
    pdf.add_attachment('note.txt', b'synthetic private attachment')
    pdf.write(source)
    job_root = tmp_path / 'jobs'
    job_root.mkdir()
    marker = tmp_path / 'attachment-started.json'
    monkeypatch.setattr(jobs_module, 'worker', paused_attachment_worker)
    jobs = Jobs(timeout=8 if cancel else 3, temp_root=str(job_root))

    async def scenario():
        task = asyncio.create_task(jobs.run('file', source.getvalue(), 'sample.pdf'))
        for _ in range(100):
            if marker.exists():
                break
            if task.done():
                await task
            await asyncio.sleep(0.02)
        assert marker.exists(), 'Real qpdf extraction did not reach the test checkpoint'
        staged = json.loads(marker.read_text())
        assert staged['bytes'] == len(b'synthetic private attachment')
        extracted = Path(staged['path'])
        assert extracted.is_relative_to(job_root)
        assert extracted.read_bytes() == b'synthetic private attachment'
        if cancel:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            with pytest.raises(JobError) as exc:
                await task
            assert exc.value.code == 'processing_timeout'
        assert not extracted.exists()

    asyncio.run(scenario())
    assert jobs.active == 0
    assert list(job_root.iterdir()) == []
