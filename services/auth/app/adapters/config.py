from app.domain.ports.config import ConfigPort
from app.infrastructure.settings import settings


class SettingsConfigPort(ConfigPort):
    
    def get_email_token_expiry(self):
        return settings.email_token_expiry
    
    def get_email_token_length(self):
        return settings.email_token_length
