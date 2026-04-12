# Nocturn

AI-powered note-taking application with semantic search and an intelligent assistant that can create, edit, and organize your notes.

## Features

- **Markdown notes** with auto-save, soft-delete/restore, and version-based conflict detection
- **Tag system** for filtering and organizing notes
- **AI assistant** chat with SSE streaming, proposals (edit/create/delete notes, manage tags), and bulk operations with user confirmation
- **Semantic search (RAG)** powered by vector embeddings and cosine similarity
- **Authentication** with JWT access/refresh tokens, email confirmation, and password reset
- **Dark/light theme**, keyboard shortcuts, resizable panels, drag-and-drop tabs
- **Internationalization** (English and Russian)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, TypeScript, Vite 8, Tailwind CSS 4, Radix UI, CodeMirror 6 |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2 (async), Alembic |
| Database | PostgreSQL 16 with pgvector |
| Cache | Redis |
| LLM | RouterAI (OpenAI-compatible API) |
| Email | Resend |
| Auth | JWT (PyJWT) + Argon2 password hashing |
| Proxy | Nginx |
| Containers | Docker Compose |

## Architecture

```
                  :80/:443
                     |
                   Nginx
                  /     \
          /api/*          /*
            |              |
    FastAPI backend    React frontend
     (Uvicorn:8000)    (static/Nginx:80)
        |      |
   PostgreSQL  Redis
   (pgvector)
        |
      Worker
  (embeddings + cleanup)
```

**Backend modules** follow a consistent `models -> repository -> service -> router -> schemas` pattern:

```
backend/src/app/modules/
  auth/       Registration, login, JWT, email verification
  profile/    Nickname, password change, account deletion
  notes/      CRUD, soft-delete, restore, tags, versioning
  tags/       User-scoped labels
  rag/        Chunking, embedding, semantic search
  ai/         Chat sessions, SSE streaming, proposals, bulk ops
  admin/      User management, role control
```

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- (Optional for local frontend dev) Node.js 20+

### 1. Clone and configure

```bash
git clone https://github.com/CaseyJohnson-RS/nocturn && cd Nocturn
cp .env.example .env
```

Edit `.env` and set at minimum:

```dotenv
JWT_SECRET=<random-string-at-least-32-chars>
ROUTERAI_API_KEY=<your-key>
ROUTERAI_LLM_MODEL=<model-name>
ROUTERAI_EXECUTOR_MODEL=<model-name>
ROUTERAI_EMBEDDING_MODEL=<model-name>
```

### 2. Launch

```bash
docker compose up
```

This starts all services: Nginx, backend, worker, frontend, PostgreSQL, and Redis.

The app is available at **http://localhost**. The API docs are at **http://localhost/api/docs**.

On first launch the backend runs Alembic migrations automatically and seeds an admin account using `ADMIN_EMAIL` / `ADMIN_PASSWORD` from `.env`.

### 3. Stop

```bash
docker compose down
```

Add `-v` to also remove the database volume.

## Development

### Frontend (standalone)

```bash
cd frontend
npm install
npm run dev
```

Vite starts on `http://localhost:5173` and proxies `/api/*` requests to `http://localhost:80` (Nginx), so the Docker backend must be running.

### Backend

The backend runs inside Docker. To view logs:

```bash
docker compose logs -f backend
docker compose logs -f worker
```

### Testing

```bash
# Start isolated test infrastructure
docker compose -f docker-compose.test.yml up -d

# Run backend tests
cd backend
uv run pytest
```

### Linting

```bash
# Frontend
cd frontend && npm run lint

# Backend
cd backend && uv run ruff check .
```

## Environment Variables

All configuration is via `.env` (loaded by Docker Compose). See [`.env.example`](.env.example) for the full list. Key groups:

| Group | Variables |
|-------|-----------|
| Database | `DATABASE_URL`, `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW` |
| Redis | `REDIS_URL` |
| JWT | `JWT_SECRET`, `ACCESS_TOKEN_TTL_MINUTES`, `REFRESH_TOKEN_TTL_DAYS` |
| LLM | `ROUTERAI_API_KEY`, `ROUTERAI_BASE_URL`, `ROUTERAI_LLM_MODEL`, `ROUTERAI_EMBEDDING_MODEL` |
| Email | `EMAIL_PROVIDER`, `EMAIL_API_KEY`, `EMAIL_FROM` |
| Admin seed | `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_NICKNAME` |
| Limits | `MAX_NOTES_PER_USER`, `MAX_CHAT_SESSIONS_PER_USER`, `TRASH_RETENTION_DAYS`, etc. |
| Rate limiting | `RATE_AUTH_PER_MINUTE`, `RATE_CRUD_PER_MINUTE`, `RATE_AI_PER_MINUTE`, etc. |
| Worker | `EMBEDDING_QUEUE_INTERVAL_SECONDS`, `CLEANUP_INTERVAL_SECONDS` |

## API

The backend exposes a REST API with OpenAPI documentation:

- **Swagger UI**: http://localhost/api/docs
- **OpenAPI JSON**: http://localhost/api/openapi.json

### AI Streaming Protocol

`POST /api/ai/sessions/{id}/messages` returns an SSE stream (`text/event-stream`):

| Event | Payload | Description |
|-------|---------|-------------|
| `ai:text_delta` | `{"delta": "..."}` | Incremental text chunk |
| `ai:proposal` | `{Proposal}` | Proposed note action |
| `ai:pending_confirmation` | `{PendingConfirmation}` | Bulk op awaiting confirmation |
| `ai:error` | `{"code": "...", "message": "..."}` | Error during generation |
| `ai:done` | `{"message": {Message}}` | Stream complete |

## Project Structure

```
Nocturn/
  backend/
    src/
      app/              FastAPI application
        common/         Shared: DB engine, Redis, email, dependencies
        middleware/      Auth extraction, rate limiting
        modules/        Feature modules (auth, notes, ai, rag, etc.)
      worker/           Background tasks (embeddings, cleanup)
    migrations/         Alembic database migrations
    pyproject.toml      Python dependencies
  frontend/
    src/
      api/              HTTP client, endpoint wrappers, types
      components/       UI components (chat, editor, layout, ui)
      stores/           React Context state (auth, notes, chat, tabs, theme, i18n)
      pages/            Auth pages (login, register, confirm, forgot password)
      hooks/            Custom hooks (keyboard shortcuts)
      i18n/             Translations (en, ru)
      layouts/          App layout wrapper
    package.json        Node dependencies
  nginx/
    nginx.conf          Reverse proxy config
  docs/                 SRS, SAD, CPS, AIS documentation
  docker-compose.yml    Production stack
  .env.example          Environment template
  Makefile              Dev shortcuts
```
