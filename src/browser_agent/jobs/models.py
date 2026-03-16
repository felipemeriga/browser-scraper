from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ProviderResult(BaseModel):
    status: str
    file_path: str | None = None
    extracted_data: dict[str, Any] | None = None
    error: str | None = None


class Job(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    provider: str
    action: str
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    result: ProviderResult | None = None
