from contextlib import asynccontextmanager

from fastapi import FastAPI

from browser_agent.api.router import job_manager, router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await job_manager.cancel_all()


app = FastAPI(title="Browser Agent", version="0.1.0", lifespan=lifespan)
app.include_router(router)
