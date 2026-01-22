from app.adapters.config import SettingsConfigPort


def get_config() -> SettingsConfigPort:
    from app.adapters.config import SettingsConfigPort
    return SettingsConfigPort()