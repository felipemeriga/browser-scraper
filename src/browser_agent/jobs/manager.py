import asyncio
from datetime import datetime, timezone

from browser_agent.config import settings
from browser_agent.jobs.models import Job, JobStatus, ProviderResult


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_tasks)

    def create_job(self, provider: str, action: str) -> Job:
        job = Job(provider=provider, action=action)
        self._jobs[job.id] = job
        return job

    def get_job(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list_jobs(self, status: JobStatus | None = None) -> list[Job]:
        jobs = list(self._jobs.values())
        if status is not None:
            jobs = [j for j in jobs if j.status == status]
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)

    def run_job(
        self,
        job: Job,
        coro: asyncio.coroutines,
    ) -> None:
        task = asyncio.create_task(self._execute(job, coro))
        self._tasks[job.id] = task

    async def _execute(self, job: Job, coro: asyncio.coroutines) -> None:
        job.status = JobStatus.RUNNING
        try:
            async with asyncio.timeout(settings.job_timeout_seconds):
                async with self._semaphore:
                    result = await coro
            job.status = JobStatus.COMPLETED
            job.result = result
        except TimeoutError:
            job.status = JobStatus.FAILED
            job.result = ProviderResult(status="failure", error="Job timed out")
        except asyncio.CancelledError:
            job.status = JobStatus.FAILED
            job.result = ProviderResult(status="failure", error="Job cancelled")
        except Exception as e:
            job.status = JobStatus.FAILED
            job.result = ProviderResult(status="failure", error=str(e))
        finally:
            job.completed_at = datetime.now(timezone.utc)
            self._tasks.pop(job.id, None)

    async def cancel_all(self) -> None:
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
