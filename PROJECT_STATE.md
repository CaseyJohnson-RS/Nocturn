# Nocturn Project State

## Last Saved State
- Date: 2026-04-01
- Branch: `phase/4-ai` (current working branch, merged into `main`)

## Repository Overview

Nocturn is an AI-powered note-taking application with semantic search and an AI assistant that proposes actions on notes (user confirmation required before any mutation).

### Tech Stack
- **Backend:** Python 3.12, FastAPI, async SQLAlchemy (asyncpg), PostgreSQL + pgvector, Redis
- **LLM/Embedding:** RouterAI (OpenAI-compatible API) for chat completions and embeddings
- **Email:** Resend / Brevo HTTP API via httpx (gracefully skips in dev if no API key)
- **Frontend:** React (separate `frontend/` directory, not modified in backend sessions)
- **Deployment:** Docker Compose (nginx, backend, worker, frontend, postgres, redis)
- **Testing:** pytest + pytest-asyncio, Docker-native test runner (`docker-compose.test.yml`)

### Directory Structure
```
backend/
  app/
    common/          # database, redis, routerai client, email, exceptions, dependencies
    config.py        # All env settings (from CPS)
    main.py          # FastAPI app with lifespan, CORS, rate limiting
    seed.py          # Admin seed on first launch
    middleware/       # auth (JWT), rate_limit (Redis sliding window)
    modules/
      auth/          # Registration, login, refresh, logout, password reset, email confirmation
      profile/       # Nickname change, password change, account deactivation
      notes/         # CRUD with soft delete, optimistic locking, tag management, batch get
      tags/          # User tag CRUD, case-insensitive uniqueness
      rag/           # Chunking, embedding queue, semantic search (pgvector cosine)
      ai/            # Chat sessions, Planner tool-loop, proposals, bulk operations, Executor
      admin/         # User listing, block/unblock, role management
  worker/
    main.py          # Background worker: embedding queue + 5 cleanup tasks
  migrations/
    versions/        # 001 auth, 002 notes+tags, 003 rag, 004 ai tables
  tests/             # 167 tests across 10 test files
```

## Backend Modules — Implementation Status

### AUTH (complete)
- Registration with email confirmation (token-based)
- Login with JWT access token (15min) + refresh token (14d, HttpOnly cookie)
- Refresh token rotation with session limits (5 per user)
- Password reset via email link
- Argon2id password hashing
- Rate limiting: IP-based for auth endpoints

### PROFILE (complete)
- Nickname change, password change, profile view
- Account deactivation (sets `is_active = false`)

### NOTES (complete)
- CRUD with soft delete (30-day trash retention)
- Optimistic locking via `version` column
- Tag assignment (`PUT /notes/{id}/tags`)
- Batch get (`POST /notes/batch`, max 50 IDs) — used by AI proposals UI
- Auto-save support (5s interval, frontend responsibility)
- Max 3000 notes per user, max 20000 chars per note

### TAGS (complete)
- CRUD with case-insensitive per-user uniqueness
- Max 100 tags per user, max 10 tags per note

### RAG (complete)
- Text chunking: 500 tokens per chunk, 50 token overlap, title prefix
- Embedding queue: pending -> processing -> done/failed (max 3 retries)
- Semantic search: pgvector cosine distance with HNSW index
- Integration with notes module: auto-index on create/update, remove on soft-delete, re-index on restore

### AI (complete — action lifecycle just implemented)

#### Planner (main LLM)
- Multi-turn tool-calling loop (up to 10 rounds per message)
- 13 tools via OpenAI function calling:
  - **Read tools (3):** `search_notes` (semantic/fulltext with filters), `get_note`, `list_tags`
  - **Proposal tools (5):** `propose_edit_note`, `propose_create_note`, `propose_delete_note`, `propose_add_tags`, `propose_remove_tags`
  - **Batch tools (5):** `batch_add_tags`, `batch_remove_tags`, `batch_delete`, `batch_replace` (RE2 regex), `batch_transform` (LLM-based)
- SSE events: `ai:text_delta`, `ai:proposal`, `ai:pending_confirmation`, `ai:error`, `ai:done`

#### Executor (cheaper LLM, for batch_transform)
- One-shot per note: system prompt with instruction + note content
- 4 tools: `edit_note`, `add_tags`, `remove_tags`, `delete_note`
- Tool calls become proposals (no feedback loop)

#### Proposal Lifecycle (AIS 5)
- Status flow: `pending` -> `applied` | `dismissed`
- `PATCH /sessions/{id}/messages/{msg_id}/actions/{action_id}` with `{ status: "applied" | "dismissed" }`
- On finalize: `data` cleared, `summary` generated deterministically (AIS 2.5 templates)
- Deduplication: max one proposal per type per note per response
- Client applies mutations via standard NOTES CRUD after marking proposal as applied

#### Bulk Operations (AIS 6)
- Pending confirmation flow: Planner registers `pending_confirmation` -> user confirms/dismisses
- `POST /sessions/{id}/confirm/{confirmation_id}` — executes bulk, streams generated proposals via SSE
- `POST /sessions/{id}/dismiss/{confirmation_id}` — marks as dismissed with summary
- Deterministic batches: `batch_add_tags`, `batch_remove_tags`, `batch_delete`, `batch_replace` — backend generates proposals without LLM
- Non-deterministic: `batch_transform` — Executor called per note

#### Concurrency & Control
- Redis generating flag (`generating:{session_id}`, NX + 120s TTL)
- `POST /sessions/{id}/cancel` — clears flag, partial results preserved
- New session with `dismiss_session_id` auto-dismisses pending proposals (AIS 10.2)
- Pre-validation before SSE stream start (returns JSON 404/400/409 instead of raising inside generator)

#### Context Formation (AIS 7)
- System prompt with rules, current date, tool descriptions
- History: newest-first, token-budgeted, max 25 messages
- Attached note previews on last user message only
- Actions summarized as text (not full snapshots) in history

### ADMIN (complete)
- User listing, block/unblock, role management
- Admin-only endpoints protected by role check

### EMAIL (complete)
- Resend and Brevo provider support via httpx (no SDK)
- Wired into: registration, password reset, confirmation resend
- Gracefully skips if `EMAIL_API_KEY` not set (dev mode)

### WORKER (complete)
- Embedding queue processing (30s interval)
- 5 cleanup tasks (1h interval):
  1. Purge expired trashed notes (with RAG chunk cleanup)
  2. Purge expired refresh tokens
  3. Purge expired verification tokens
  4. Purge stale unconfirmed accounts (72h)
  5. Purge expired chat sessions (14d)

## API Endpoints

### Auth (`/api/auth`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/register` | Register new user |
| POST | `/login` | Login, returns access + refresh token |
| POST | `/refresh` | Rotate refresh token |
| POST | `/logout` | Revoke refresh token |
| GET | `/me` | Current user profile |
| POST | `/confirm-email` | Confirm email with token |
| POST | `/resend-confirmation` | Resend confirmation email |
| POST | `/request-password-reset` | Send password reset email |
| POST | `/reset-password` | Reset password with token |

### Profile (`/api/profile`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | View profile |
| PUT | `/nickname` | Change nickname |
| PUT | `/password` | Change password |
| POST | `/deactivate` | Deactivate account |

### Notes (`/api/notes`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/` | Create note |
| GET | `/` | List notes (with filters, pagination) |
| GET | `/{id}` | Get note |
| PUT | `/{id}` | Update note (optimistic locking) |
| DELETE | `/{id}` | Soft/hard delete |
| POST | `/{id}/restore` | Restore from trash |
| PUT | `/{id}/tags` | Set note tags |
| POST | `/batch` | Batch get notes by IDs |

### Tags (`/api/tags`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/` | Create tag |
| GET | `/` | List tags |
| PUT | `/{id}` | Rename tag |
| DELETE | `/{id}` | Delete tag |

### AI (`/api/ai`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/sessions` | Create chat session |
| GET | `/sessions` | List sessions |
| GET | `/sessions/{id}` | Get session with messages |
| PUT | `/sessions/{id}` | Rename session |
| DELETE | `/sessions/{id}` | Delete session |
| POST | `/sessions/{id}/messages` | Send message (SSE stream) |
| POST | `/sessions/{id}/cancel` | Cancel active generation |
| PATCH | `/sessions/{id}/messages/{msg_id}/actions/{action_id}` | Apply/dismiss proposal |
| POST | `/sessions/{id}/confirm/{conf_id}` | Confirm bulk operation (SSE stream) |
| POST | `/sessions/{id}/dismiss/{conf_id}` | Dismiss bulk operation |

### RAG (`/api/rag`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/search` | Semantic search |

### Admin (`/api/admin`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/users` | List all users |
| PATCH | `/users/{id}/block` | Block user |
| PATCH | `/users/{id}/unblock` | Unblock user |
| PATCH | `/users/{id}/role` | Change user role |
| DELETE | `/users/{id}` | Delete user |

## Database Schema (4 migrations)

### 001: Auth tables
- `users` (id, email, hashed_password, nickname, role, is_email_confirmed, is_active, timestamps)
- `refresh_tokens` (id, user_id FK, token_hash, expires_at, timestamps)
- `verification_tokens` (id, user_id FK, token_hash, type, expires_at, timestamps)

### 002: Notes + Tags tables
- `notes` (id, user_id FK, title, content, version, timestamps, deleted_at)
- `tags` (id, user_id FK, name, created_at) — unique index on `(user_id, lower(name))`
- `note_tags` (note_id FK, tag_id FK) — M:N junction

### 003: RAG tables
- `note_chunks` (id, note_id, user_id, chunk_index, content, embedding vector, is_deleted)
- `embedding_tasks` (id, note_id UNIQUE, status, error, attempts, timestamps)
- HNSW index on embeddings with partial filter `WHERE is_deleted = false`

### 004: AI tables
- `chat_sessions` (id, user_id FK, title, timestamps)
- `chat_messages` (id, session_id FK, role, content, sources, actions JSONB, attached_note_ids UUID[], token_estimate, created_at)

## Testing

### Test Infrastructure
- `docker-compose.test.yml` with `pgvector:pg16`, `redis:alpine`, and `backend-test` (INSTALL_DEV=true)
- `conftest.py`: session-scoped DB setup, per-test table truncation, Redis flush, test lifespan, DB session override
- Environment overridable via `os.environ.setdefault()` for Docker compose

### Test Coverage (167 tests)
| File | Tests | Covers |
|------|-------|--------|
| `test_auth_integration.py` | Auth registration, login, refresh, logout, password reset, email confirmation |
| `test_auth_unit.py` | Password validation, token hashing, JWT |
| `test_notes_integration.py` | Note CRUD, soft delete, restore, tags, optimistic locking, batch get |
| `test_tags_integration.py` | Tag CRUD, case-insensitive uniqueness, limits |
| `test_profile_integration.py` | Nickname, password change, deactivation |
| `test_admin_integration.py` | User listing, block/unblock, role management |
| `test_rag_integration.py` | Chunking, embedding queue, semantic search |
| `test_ai_integration.py` | Sessions, streaming, proposals (apply/dismiss/double-apply), bulk dismiss, cancel, concurrency guard, tool executor, summary generation |
| `test_routerai_unit.py` | Embeddings, streaming, model context length, ChatCompletionAccumulator, tool-call collection |

## Key Files for Current Work

### AI Module (most recently changed)
- `backend/app/modules/ai/tools.py` — **NEW**: 13 Planner + 4 Executor tool schemas, ToolExecutor class, summary templates, deterministic batch proposal generation
- `backend/app/modules/ai/service.py` — Planner multi-turn loop, SSE events, proposal lifecycle, bulk confirm/dismiss, Executor one-shot, Redis concurrency guard
- `backend/app/modules/ai/router.py` — All AIS endpoints: PATCH actions, confirm/dismiss bulk, cancel
- `backend/app/modules/ai/repository.py` — `find_action_by_id()` for cross-message action lookup
- `backend/app/modules/ai/schemas.py` — `UpdateActionRequest`, `CreateSessionRequest` with `dismiss_session_id`
- `backend/app/common/routerai.py` — `ToolCall`, `ChatCompletionAccumulator`, tool-aware `chat_completion_stream()`

### Configuration
- `backend/app/config.py` — All settings from CPS
- `.env.example` — All environment variables with defaults

## Commit History (main)
```
c41b444 Polish backend: email delivery, action proposals, worker cleanup, Docker tests
6d94b6d Add AI assistant module: chat sessions, RAG context, SSE streaming
80c943a Fix startup crash: run Alembic migrations via subprocess
f3533f5 Add RAG module: chunking, embeddings, semantic search, and worker
c12ede7 Add admin module: user listing, block/unblock, role management
6b15fcd Add profile module: nickname, password change, account deactivation
... (34 commits total from initial scaffold to current)
```

## Next Work Items
1. Frontend handling for AI SSE events (`ai:text_delta`, `ai:proposal`, `ai:pending_confirmation`, `ai:done`)
2. Frontend proposal cards: apply/dismiss UI with CRUD calls to NOTES module
3. Frontend bulk confirmation UI
4. Conversation memory summarization (currently old messages are dropped, not summarized)
5. Message editing / regeneration
6. Streaming cancellation from client side (abort signal)
7. Full Docker-native integration testing (backend API + frontend in container)

## Architecture Notes
- Planner uses standard OpenAI function calling (not `<ACTIONS>` tags) for all mutations
- Proposals stored in `chat_messages.actions` JSONB with full snapshot while pending, summary-only after finalize
- Client is responsible for executing the actual CRUD mutation after marking a proposal as applied (PATCH then PUT/POST/DELETE)
- Redis `generating:{session_id}` key prevents concurrent operations per session
- Token budget: `model_context - system_prompt_tokens - safety_margin`, configurable via env
- RE2 regex engine for `batch_replace` (ReDoS-safe, no lookahead/lookbehind)
- Worker runs in separate container with same image, different entrypoint
