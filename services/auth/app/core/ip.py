from fastapi import Request
from app.core.settings import settings


def get_client_ip(request: Request) -> str:
    """
    Возвращает IP клиента.
    """
    if settings.trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    
    if request.client is not None:
        return request.client.host
    
    return "0.0.0.0"
