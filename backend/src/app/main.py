import logging
import os
import subprocess
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.app.common.database.engine import async_session_factory, engine
from src.app.common.email import init_email_service
from src.app.common.observability.logging import setup_logging
from src.app.common.observability.metrics import set_build_info
from src.app.common.observability.middleware import ObservabilityMiddleware
from src.app.common.redis import redis_client
from src.app.config import settings
from src.app.middleware.rate_limit import RateLimitMiddleware
from src.app.modules.admin.router import router as admin_router
from src.app.modules.ai.router import router as ai_router
from src.app.modules.auth.router import router as auth_router
from src.app.modules.notes.router import router as notes_router
from src.app.modules.profile.router import router as profile_router
from src.app.modules.rag.router import router as rag_router
from src.app.modules.system.router import router as system_router
from src.app.modules.tags.router import router as tags_router
from src.app.seed import seed_admin

APP_VERSION = "0.1.0"

setup_logging("api")
logger = logging.getLogger(__name__)


# Migrations belong to the deploy pipeline, not to application startup: with
# more than one replica every instance races on `alembic upgrade head`, and a
# bad migration crash-loops the whole service instead of failing one deploy
# step. `make migrate` (and the `migrate` compose service) runs this now.
# RUN_MIGRATIONS_ON_STARTUP=true keeps the old behaviour for single-instance
# platforms that have no separate release phase.
def _run_migrations() -> None:
    logger.info("Running database migrations")
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    set_build_info(service="api", version=APP_VERSION, commit=os.getenv("GIT_COMMIT", "unknown"))

    if os.getenv("RUN_MIGRATIONS_ON_STARTUP", "true").lower() == "true":
        _run_migrations()

    async with async_session_factory() as session:
        await seed_admin(session)

    init_email_service()

    logger.info("API startup complete", extra={"version": APP_VERSION})

    yield

    # Shutdown: uvicorn has already stopped accepting connections and drained
    # in-flight requests by this point, so it is safe to close the pools.
    logger.info("API shutting down, releasing connections")
    await engine.dispose()
    await redis_client.aclose()


APP_DESCRIPTION = """\
**Nocturn** — AI-powered note-taking application with semantic search
and an intelligent assistant that can create, edit, and organize your notes.

## Core concepts

| Concept | Description |
|---------|-------------|
| **Note** | Markdown document with title, content, version counter, and tags. Supports soft-delete (trash) and restore. |
| **Tag** | User-scoped label attached to notes for filtering and organization. |
| **AI Session** | Chat conversation with the AI assistant. Each session holds an ordered list of messages. |
| **Proposal** | An action the AI suggests (edit/create/delete a note, add/remove tags). The user can **apply** or **dismiss** each proposal. |
| **Pending Confirmation** | A bulk operation (e.g. "add tag X to 10 notes") that requires explicit user confirmation before execution. |

## Authentication

All endpoints except `/api/auth/register`, `/api/auth/login`, and `/api/health`
require a valid JWT access token in the `Authorization: Bearer <token>` header.

- **Access token** — short-lived JWT returned by `POST /api/auth/login`.
- **Refresh token** — long-lived, stored in an httponly cookie (`path=/api/auth`).
  Use `POST /api/auth/refresh` to obtain a new access token.

## AI streaming protocol

`POST /api/ai/sessions/{id}/messages` returns an **SSE stream** (`text/event-stream`).

Each SSE frame has the format:
```
event: <type>
data: <json>
```

Event types:

| Event | Payload | Description |
|-------|---------|-------------|
| `ai:text_delta` | `{"delta": "..."}` | Incremental text chunk from the assistant |
| `ai:proposal` | `{Proposal}` | Proposed note action |
| `ai:pending_confirmation` | `{PendingConfirmation}` | Bulk operation awaiting user confirmation |
| `ai:error` | `{"code": "...", "message": "..."}` | Error during generation |
| `ai:done` | `{"message": {Message}}` | Stream complete with the final saved message |

## Optimistic concurrency

Note updates use version-based concurrency control.
The client must send the current `version` — if it doesn't match the server's
version, a `409 Conflict` is returned.

## Semantic search (RAG)

Notes are chunked and embedded asynchronously by a background worker.
`POST /api/rag/search` performs cosine-similarity search over embeddings.
Newly created/edited notes may take up to 30 seconds to become searchable.
"""  # noqa: E501

app = FastAPI(
    title="Nocturn",
    summary="AI-powered note-taking API",
    description=APP_DESCRIPTION,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    openapi_tags=[
        {
            "name": "auth",
            "description": "Registration, login, JWT tokens, email confirmation, password reset.",
        },
        {
            "name": "profile",
            "description": "Current user profile management — nickname, password, "
            "account deletion.",
        },
        {
            "name": "notes",
            "description": "CRUD for markdown notes with tags, soft-delete/restore, "
            "and batch operations.",
        },
        {
            "name": "tags",
            "description": "User-scoped tags for note organization and filtering.",
        },
        {
            "name": "rag",
            "description": "Semantic (vector) search over note embeddings.",
        },
        {
            "name": "ai",
            "description": "AI chat sessions, SSE message streaming, proposals, "
            "and bulk confirmations.",
        },
        {
            "name": "admin",
            "description": "User management for administrators — list users, change roles, "
            "enable/disable accounts.",
        },
    ],
)

app.add_middleware(RateLimitMiddleware)
# Added last => outermost layer: rate-limit rejections (429) are counted as
# real responses, and every log line inside the request carries a request_id.
app.add_middleware(ObservabilityMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(notes_router)
app.include_router(tags_router)
app.include_router(rag_router)
app.include_router(ai_router)
app.include_router(admin_router)
app.include_router(system_router)


@app.get(
    "/api/health",
    summary="Health check",
    tags=["system"],
)
async def health_check():
    """Returns `{"status": "ok"}` if the API server is running.

    Does not check database or Redis connectivity — use this endpoint
    only for basic liveness probes.
    """
    return {"status": "ok"}


@app.get("/", summary="Funny health check", tags=["system"])
async def funny_health_check(name: str = "world", message: str = "Let's be friends!"):
    return f"Hello {name}! {message}"
