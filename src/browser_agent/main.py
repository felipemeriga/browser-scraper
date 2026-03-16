from contextlib import asynccontextmanager

from fastapi import FastAPI

from browser_agent.api.router import job_manager, router
from browser_agent.providers.claro import ClaroProvider
from browser_agent.providers.copel import CopelProvider
from browser_agent.providers.countfly import CountflyProvider
from browser_agent.providers.registry import registry
from browser_agent.providers.sanepar import SaneparProvider


def _register_providers() -> None:
    registry.register(CopelProvider())
    registry.register(ClaroProvider())
    registry.register(SaneparProvider())
    registry.register(CountflyProvider())


@asynccontextmanager
async def lifespan(app: FastAPI):
    _register_providers()
    yield
    await job_manager.cancel_all()


app = FastAPI(title="Browser Agent", version="0.1.0", lifespan=lifespan)
app.include_router(router)
