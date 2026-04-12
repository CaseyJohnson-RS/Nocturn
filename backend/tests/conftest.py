import os

os.environ["DATABASE_URL"] = "postgresql+asyncpg://nocturn:nocturn_test@localhost:5433/nocturn_test"
os.environ["DATABASE_ECHO"] = "False"
os.environ["DATABASE_POOL_SIZE"] = "10"
os.environ["DATABASE_MAX_OVERFLOW"] = "5"

os.environ["REDIS_URL"] = "redis://localhost:6380/0"

os.environ["JWT_SECRET"] = "test-secret-key-at-least-32-characters-long"
os.environ["ACCESS_TOKEN_TTL_MINUTES"] = "15"
os.environ["REFRESH_TOKEN_TTL_DAYS"] = "14"
os.environ["MAX_SESSIONS_PER_USER"] = "5"

os.environ["ROUTERAI_API_KEY"] = "test-routerai-key"
os.environ["ROUTERAI_BASE_URL"] = "http://localhost:8001/api/v1"
os.environ["ROUTERAI_LLM_MODEL"] = "test-llm-model"
os.environ["ROUTERAI_LLM_CONTEXT_WINDOW"] = "8192"
os.environ["ROUTERAI_FETCH_MODEL_CONTEXT_WINDOW"] = "false"
os.environ["ROUTERAI_EXECUTOR_MODEL"] = "test-executor-model"
os.environ["ROUTERAI_EMBEDDING_MODEL"] = "test-embedding-model"

os.environ["EMAIL_PROVIDER"] = "mock"
os.environ["EMAIL_API_KEY"] = "test-email-key"
os.environ["EMAIL_FROM"] = "noreply@nocturn.example.com"

os.environ["ADMIN_EMAIL"] = "admin@example.com"
os.environ["ADMIN_PASSWORD"] = "ChangeMe123"
os.environ["ADMIN_NICKNAME"] = "admin"

os.environ["FRONTEND_URL"] = "http://localhost:3000"

os.environ["EMAIL_CONFIRM_TTL_HOURS"] = "2"
os.environ["PASSWORD_RESET_TTL_HOURS"] = "1"
os.environ["UNCONFIRMED_ACCOUNT_TTL_HOURS"] = "24"

os.environ["MAX_NOTES_PER_USER"] = "3000"
os.environ["MAX_NOTE_SIZE"] = "20000"
os.environ["MAX_TITLE_LENGTH"] = "200"
os.environ["MAX_TAGS_PER_NOTE"] = "10"
os.environ["TRASH_RETENTION_DAYS"] = "30"
os.environ["AUTOSAVE_INTERVAL_SECONDS"] = "5"

os.environ["MAX_TAGS_PER_USER"] = "100"

os.environ["MAX_MESSAGE_LENGTH"] = "4000"
os.environ["MAX_SOURCES_PER_RESPONSE"] = "5"
os.environ["MAX_CHAT_SESSIONS_PER_USER"] = "50"
os.environ["CHAT_SESSION_TTL_DAYS"] = "14"
os.environ["LLM_FIRST_TOKEN_TIMEOUT_SECONDS"] = "10"
os.environ["MAX_NOTES_IN_BULK"] = "25"
os.environ["MAX_ATTACHED_NOTES"] = "10"
os.environ["MAX_MESSAGES_IN_CONTEXT"] = "25"
os.environ["SYSTEM_PROMPT_TOKENS"] = "500"
os.environ["SAFETY_MARGIN_TOKENS"] = "500"
os.environ["PLANNER_CHARS_PER_TOKEN"] = "1.3"

os.environ["EMBEDDING_MAX_ATTEMPTS"] = "3"
os.environ["EMBEDDING_DEBOUNCE_MINUTES"] = "2"

os.environ["EMBEDDING_QUEUE_INTERVAL_SECONDS"] = "30"
os.environ["CLEANUP_INTERVAL_SECONDS"] = "3600"

os.environ["RATE_AUTH_PER_MINUTE"] = "20"
os.environ["RATE_EMAIL_OPS_PER_MINUTE"] = "5"
os.environ["RATE_VERIFY_PER_MINUTE"] = "5"
os.environ["RATE_REFRESH_PER_MINUTE"] = "15"
os.environ["RATE_CRUD_PER_MINUTE"] = "120"
os.environ["RATE_AI_PER_MINUTE"] = "15"

os.environ["CHUNK_SIZE_TOKENS"] = "500"
os.environ["CHUNK_OVERLAP_TOKENS"] = "50"
os.environ["EMBEDDING_DIMENSIONS"] = "2560"