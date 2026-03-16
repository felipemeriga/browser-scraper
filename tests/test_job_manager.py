import asyncio

import pytest

from browser_agent.jobs.manager import JobManager
from browser_agent.jobs.models import JobStatus, ProviderResult


@pytest.fixture
def manager():
    return JobManager()


def test_create_job(manager: JobManager):
    job = manager.create_job("copel", "fetch-bill")
    assert job.provider == "copel"
    assert job.action == "fetch-bill"
    assert job.status == JobStatus.PENDING
    assert job.id is not None


def test_get_job(manager: JobManager):
    job = manager.create_job("copel", "fetch-bill")
    found = manager.get_job(job.id)
    assert found is not None
    assert found.id == job.id


def test_get_job_not_found(manager: JobManager):
    assert manager.get_job("nonexistent") is None


def test_list_jobs(manager: JobManager):
    manager.create_job("copel", "fetch-bill")
    manager.create_job("claro", "fetch-bill")
    jobs = manager.list_jobs()
    assert len(jobs) == 2


def test_list_jobs_filter_by_status(manager: JobManager):
    manager.create_job("copel", "fetch-bill")
    job2 = manager.create_job("claro", "fetch-bill")
    job2.status = JobStatus.RUNNING

    pending = manager.list_jobs(status=JobStatus.PENDING)
    assert len(pending) == 1
    assert pending[0].provider == "copel"


async def test_run_job_success(manager: JobManager):
    job = manager.create_job("copel", "fetch-bill")

    async def fake_execute():
        return ProviderResult(status="success", file_path="/tmp/bill.pdf")

    manager.run_job(job, fake_execute())
    await asyncio.sleep(0.1)

    assert job.status == JobStatus.COMPLETED
    assert job.result is not None
    assert job.result.status == "success"
    assert job.completed_at is not None


async def test_run_job_failure(manager: JobManager):
    job = manager.create_job("copel", "fetch-bill")

    async def failing_execute():
        raise RuntimeError("Browser crashed")

    manager.run_job(job, failing_execute())
    await asyncio.sleep(0.1)

    assert job.status == JobStatus.FAILED
    assert job.result is not None
    assert "Browser crashed" in job.result.error


async def test_cancel_all(manager: JobManager):
    job = manager.create_job("copel", "fetch-bill")

    async def slow_execute():
        await asyncio.sleep(100)
        return ProviderResult(status="success")

    manager.run_job(job, slow_execute())
    await asyncio.sleep(0.05)
    await manager.cancel_all()

    assert job.status == JobStatus.FAILED
    assert len(manager._tasks) == 0
