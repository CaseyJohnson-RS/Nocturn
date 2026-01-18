from datetime import timedelta
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr

class Settings(BaseSettings):

    # Database configuration
    postgres_db: str
    postgres_user: str
    postgres_password: SecretStr
    postgres_host: str
    postgres_port: int
    postgres_echo: bool = False

    # Service configuration
    trust_proxy: bool = False
    email_token_length: int = 32
    email_token_expiry_minutes: int = 720

    # General settings
    debug: bool = False

    model_config = SettingsConfigDict(extra="ignore")

    @property
    def email_token_expiry(self) -> timedelta:
        return timedelta(minutes=self.email_token_expiry_minutes)

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://"
            f"{self.postgres_user}:{self.postgres_password.get_secret_value()}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql+psycopg2://"
            f"{self.postgres_user}:{self.postgres_password.get_secret_value()}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

# MyPy is still stupid about pydantic settings
settings = Settings()  # type: ignore[call-arg]
