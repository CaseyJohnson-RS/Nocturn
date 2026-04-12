import logging
import subprocess
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.common.database import async_session_factory, engine
from app.common.email import init_email_service
from app.common.redis import redis_client
from app.config import settings
from app.middleware.rate_limit import RateLimitMiddleware
from app.modules.admin.router import router as admin_router
from app.modules.ai.router import router as ai_router
from app.modules.auth.router import router as auth_router
from app.modules.notes.router import router as notes_router
from app.modules.profile.router import router as profile_router
from app.modules.rag.router import router as rag_router
from app.modules.tags.router import router as tags_router
from app.seed import seed_admin

logger = logging.getLogger(__name__)


def _run_migrations() -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # Startup: run migrations and seed admin
    _run_migrations()
    async with async_session_factory() as session:
        await seed_admin(session)

    init_email_service()

    yield

    # Shutdown
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
