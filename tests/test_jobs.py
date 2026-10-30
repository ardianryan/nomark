import asyncio
import os
from pathlib import Path
import subprocess

import pytest

import nomark.jobs as jobs_module
from nomark.jobs import JobError, Jobs
from tests.job_fixtures import slow_worker


def is_running(pid):
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
