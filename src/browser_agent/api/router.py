from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from browser_agent.api.schemas import (
    EmitInvoiceParams,
    HealthResponse,
    JobResponse,
    TaskRequest,
)
from browser_agent.config import settings
from browser_agent.jobs.manager import JobManager
from browser_agent.jobs.models import JobStatus
from browser_agent.providers.registry import registry

router = APIRouter()
job_manager = JobManager()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


@router.post("/tasks/{provider}/{action}", response_model=JobResponse)
async def create_task(
    provider: str,
    action: str,
    body: TaskRequest | None = None,
) -> JobResponse:
    if not registry.validate(provider, action):
        raise HTTPException(
            status_code=404,
            detail=f"Unknown provider/action: {provider}/{action}",
        )

    p = registry.get(provider)
    assert p is not None

    params = None
    if provider == "countfly" and action == "emit-invoice":
        if body is None or body.params is None:
            raise HTTPException(
                status_code=422,
                detail="countfly/emit-invoice requires params: {amount, description}",
            )
        params = EmitInvoiceParams(**body.params)

    job = job_manager.create_job(provider=provider, action=action)
    job_manager.run_job(job, p.execute(action, params))

    return _job_to_response(job)


@router.get("/jobs", response_model=list[JobResponse])
async def list_jobs(status: JobStatus | None = None) -> list[JobResponse]:
    return [_job_to_response(j) for j in job_manager.list_jobs(status)]


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str) -> JobResponse:
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_response(job)


@router.get("/downloads/{provider}/{filename}")
async def download_file(provider: str, filename: str) -> FileResponse:
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    if provider not in registry.list_providers():
        raise HTTPException(status_code=404, detail="Unknown provider")

    file_path = Path(settings.downloads_dir) / provider / filename
    resolved = file_path.resolve()
    downloads_root = Path(settings.downloads_dir).resolve()

    if not str(resolved).startswith(str(downloads_root)):
        raise HTTPException(status_code=400, detail="Invalid path")

    if not resolved.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(resolved)


def _job_to_response(job) -> JobResponse:
    download_url = None
    if job.result and job.result.file_path:
        filename = Path(job.result.file_path).name
        download_url = f"/downloads/{job.provider}/{filename}"

    return JobResponse(
        id=job.id,
        provider=job.provider,
        action=job.action,
        status=job.status,
        created_at=job.created_at,
        completed_at=job.completed_at,
        result=job.result.model_dump() if job.result else None,
        download_url=download_url,
    )
