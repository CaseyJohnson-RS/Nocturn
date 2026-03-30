import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.common.database import async_session_factory, engine
from app.common.redis import redis_client
from app.middleware.rate_limit import RateLimitMiddleware
from app.modules.auth.router import router as auth_router
from app.seed import seed_admin

logger = logging.getLogger(__name__)


def _run_migrations() -> None:
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # Startup: run migrations and seed admin
    _run_migrations()
    async with async_session_factory() as session:
        await seed_admin(session)

    yield

    # Shutdown
    await engine.dispose()
    await redis_client.aclose()


app = FastAPI(
    title="Nocturn",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)

app.include_router(auth_router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
