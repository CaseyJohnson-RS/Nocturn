# AI Module — Continuation Guide

## What's Done
- **Models**: `ChatSession`, `ChatMessage` with migration 004
- **Repository**: CRUD for sessions + messages, recent-messages with token budget
- **Service**: Full flow — save user msg → RAG context → build LLM messages → stream → save assistant msg → auto-title
- **Router**: Session CRUD + `POST /sessions/{id}/messages` (SSE streaming)
- **Tests**: 17 integration tests covering sessions, streaming, message persistence, auto-titling, note attachment, auth, isolation
- **Config**: All settings already in `config.py` (lines 56-67)

## What Needs Work Next

### 1. Token Budget (service.py `_token_budget()`)
The token budget is hardcoded at 8000. Should query the actual model context window from RouterAI or make it a config setting. Search for `# TODO: replace with actual model context window`.

### 2. Session TTL Cleanup
`chat_session_ttl_days=14` is configured but not enforced. Add a cleanup task in `worker/main.py` similar to the trash cleanup:
```python
# In run_cleanup():
session_cutoff = datetime.now(UTC) - timedelta(days=settings.chat_session_ttl_days)
# Delete sessions where updated_at < session_cutoff
```

### 3. System Prompt Refinement
The system prompt in `service.py:SYSTEM_PROMPT` is basic. Consider:
- Making it configurable (admin panel or config)
- Adding instructions about response format (markdown, code blocks)
- Adding a "personality" setting per user

### 4. Error Handling in SSE Stream
If the LLM call fails mid-stream, the error isn't communicated to the client gracefully. Add:
```python
yield f"data: {json.dumps({'error': str(e)})}\n\n"
```

### 5. Conversation Memory Summarization
When conversation history exceeds `max_messages_in_context`, older messages are just dropped. Better approach: summarize old messages into a condensed context block using the LLM.

### 6. Rate Limiting
Rate limiting at `/api/ai/` is already wired in `middleware/rate_limit.py:105-106` at `rate_ai_per_minute=10`. Works for session CRUD + messaging.

### 7. Frontend Integration
The SSE endpoint expects the frontend to:
1. `POST /api/ai/sessions` → get session_id
2. `POST /api/ai/sessions/{id}/messages` with `{ message, note_ids? }`
3. Read the `text/event-stream` response:
   - `{"delta": "chunk"}` events for streaming text
   - `{"done": true, "message": {...}}` final event with saved message metadata

### 8. Missing Features to Consider
- **Message editing**: Allow user to edit/regenerate messages
- **Streaming cancellation**: Client-side abort signal handling
- **Usage tracking**: Track token usage per user for billing/limits
- **Model selection**: Let users pick executor vs llm model
- **File/image attachments**: Beyond note references

## Architecture Reference

```
router.py (SSE endpoint)
    └─ service.py
        ├─ repository.py (session/message CRUD)
        ├─ notes_repo (fetch attached notes)
        ├─ rag.search() (semantic context)
        └─ routerai.chat_completion_stream() (LLM)
```

## Key Files
- `backend/app/modules/ai/service.py` — core logic, start here
- `backend/app/modules/ai/router.py` — HTTP endpoints
- `backend/app/common/routerai.py` — LLM API client
- `backend/app/modules/rag/service.py` — semantic search
- `backend/app/config.py:56-67` — all AI settings
- `backend/tests/test_ai_integration.py` — test patterns
