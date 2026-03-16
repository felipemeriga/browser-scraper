import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from browser_agent.api.router import job_manager
from browser_agent.jobs.models import ProviderResult
from browser_agent.main import app
from browser_agent.providers.base import BaseProvider
from browser_agent.providers.registry import registry


class FakeProvider(BaseProvider):
    name = "fake"
    actions = ["test-action"]

    async def execute(
        self, action: str, params: BaseModel | None = None
    ) -> ProviderResult:
        await asyncio.sleep(0.05)
        return ProviderResult(
            status="success",
            file_path="/app/downloads/fake/bill.pdf",
            extracted_data={"amount": 100.0},
        )


@pytest.fixture(autouse=True)
def setup_registry():
    registry.register(FakeProvider())
    yield
    registry._providers.pop("fake", None)
    job_manager._jobs.clear()
    job_manager._tasks.clear()


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_create_task(client: AsyncClient):
    resp = await client.post("/tasks/fake/test-action")
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "fake"
    assert data["action"] == "test-action"
    assert data["status"] in ("pending", "running")


async def test_create_task_unknown_provider(client: AsyncClient):
    resp = await client.post("/tasks/unknown/action")
    assert resp.status_code == 404


async def test_get_job(client: AsyncClient):
    resp = await client.post("/tasks/fake/test-action")
    job_id = resp.json()["id"]

    resp = await client.get(f"/jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == job_id


async def test_get_job_not_found(client: AsyncClient):
    resp = await client.get("/jobs/nonexistent")
    assert resp.status_code == 404


async def test_list_jobs(client: AsyncClient):
    await client.post("/tasks/fake/test-action")
    await client.post("/tasks/fake/test-action")

    resp = await client.get("/jobs")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_job_completes(client: AsyncClient):
    resp = await client.post("/tasks/fake/test-action")
    job_id = resp.json()["id"]

    await asyncio.sleep(0.2)

    resp = await client.get(f"/jobs/{job_id}")
    data = resp.json()
    assert data["status"] == "completed"
    assert data["result"]["status"] == "success"
    assert data["download_url"] == "/downloads/fake/bill.pdf"


async def test_download_unknown_provider(client: AsyncClient):
    resp = await client.get("/downloads/unknown/bill.pdf")
    assert resp.status_code == 404


async def test_download_file_not_found(client: AsyncClient):
    resp = await client.get("/downloads/fake/nonexistent.pdf")
    assert resp.status_code == 404
