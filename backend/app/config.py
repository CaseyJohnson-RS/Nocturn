from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Database ---
    database_url: str = Field(description="PostgreSQL connection string")

    # --- Redis ---
    redis_url: str = Field(default="redis://redis:6379/0")

    # --- JWT ---
    jwt_secret: str = Field(description="Secret key for JWT signing, >= 32 chars")
    access_token_ttl_minutes: int = Field(default=15)
    refresh_token_ttl_days: int = Field(default=14)
    max_sessions_per_user: int = Field(default=5)

    # --- RouterAI ---
    routerai_api_key: str = Field(default="")
    routerai_base_url: str = Field(default="https://api.routerai.ru/v1")
    routerai_llm_model: str = Field(default="")
    routerai_executor_model: str = Field(default="")
    routerai_embedding_model: str = Field(default="")

    # --- Email ---
    email_provider: str = Field(default="resend", description="resend or brevo")
    email_api_key: str = Field(default="")
    email_from: str = Field(default="noreply@nocturn.example.com")

    # --- Admin seed ---
    admin_email: str = Field(default="")
    admin_password: str = Field(default="")
    admin_nickname: str = Field(default="admin")

    # --- Frontend ---
    frontend_url: str = Field(default="http://localhost:3000")

    # --- Verification & reset ---
    email_confirm_ttl_hours: int = Field(default=24)
    password_reset_ttl_hours: int = Field(default=1)
    unconfirmed_account_ttl_hours: int = Field(default=72)

    # --- Notes ---
    max_notes_per_user: int = Field(default=3000)
    max_note_size: int = Field(default=20000)
    max_title_length: int = Field(default=200)
    max_tags_per_note: int = Field(default=10)
    trash_retention_days: int = Field(default=30)
    autosave_interval_seconds: int = Field(default=5)

    # --- Tags ---
    max_tags_per_user: int = Field(default=100)

    # --- AI assistant ---
    max_message_length: int = Field(default=4000)
    max_sources_per_response: int = Field(default=5)
    max_chat_sessions_per_user: int = Field(default=50)
    chat_session_ttl_days: int = Field(default=14)
    llm_first_token_timeout_seconds: int = Field(default=10)
    max_notes_in_bulk: int = Field(default=25)
    max_attached_notes: int = Field(default=5)
    max_messages_in_context: int = Field(default=25)
    system_prompt_tokens: int = Field(default=500)
    safety_margin_tokens: int = Field(default=500)
    planner_chars_per_token: float = Field(default=1.3)

    # --- Embedding queue ---
    embedding_max_attempts: int = Field(default=3)
    embedding_debounce_minutes: int = Field(default=2)

    # --- Worker ---
    embedding_queue_interval_seconds: int = Field(default=30)
    cleanup_interval_seconds: int = Field(default=3600)

    # --- Rate limiting ---
    rate_auth_per_minute: int = Field(default=10)
    rate_email_ops_per_minute: int = Field(default=3)
    rate_verify_per_minute: int = Field(default=5)
    rate_refresh_per_minute: int = Field(default=30)
    rate_crud_per_minute: int = Field(default=120)
    rate_ai_per_minute: int = Field(default=10)

    # --- Presence ---
    heartbeat_interval_seconds: int = Field(default=10)
    presence_ttl_seconds: int = Field(default=30)

    # --- Chunking ---
    chunk_size_tokens: int = Field(default=500)
    chunk_overlap_tokens: int = Field(default=50)


settings = Settings()  # type: ignore[call-arg]
