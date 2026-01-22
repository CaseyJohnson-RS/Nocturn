from abc import ABC, abstractmethod
from datetime import timedelta


class ConfigPort(ABC):
    @abstractmethod
    def get_email_token_length(self) -> int:
        pass

    @abstractmethod
    def get_email_token_expiry(self) -> timedelta:
        pass
