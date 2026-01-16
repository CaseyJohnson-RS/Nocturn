from datetime import timedelta
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr

class Settings(BaseSettings):

    # Database configuration
    db_name: str
    db_user: str
    db_password: SecretStr
    db_host: str
    db_port: int
    db_echo: bool = False

    # Service configuration
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
            f"{self.db_user}:{self.db_password.get_secret_value()}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql+psycopg2://"
            f"{self.db_user}:{self.db_password.get_secret_value()}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

# MyPy is still stupid about pydantic settings
settings = Settings()  # type: ignore[call-arg]
