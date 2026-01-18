from fastapi import Request
from app.core.ip import get_client_ip
from typing import NamedTuple


class RequestContext(NamedTuple):
    ip: str
    user_agent: str | None


async def get_request_context(request: Request) -> RequestContext:
    return RequestContext(
        ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent")
    )
