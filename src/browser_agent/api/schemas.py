from datetime import datetime
from typing import Any

from pydantic import BaseModel

from browser_agent.jobs.models import JobStatus


class TaskRequest(BaseModel):
    params: dict[str, Any] | None = None


class JobResponse(BaseModel):
    id: str
    provider: str
    action: str
    status: JobStatus
    created_at: datetime
    completed_at: datetime | None = None
    result: dict[str, Any] | None = None
    download_url: str | None = None


class FetchBillParams(BaseModel):
    reference_month: str  # MM/YYYY format


class ClaroFetchBillParams(BaseModel):
    product_type: str = "movel"  # "movel" or "residencial"


class EmitInvoiceParams(BaseModel):
    amount: float
    description: str


class HealthResponse(BaseModel):
    status: str = "ok"
