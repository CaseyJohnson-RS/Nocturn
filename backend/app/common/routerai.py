"""Thin async client for the RouterAI OpenAI-compatible API."""

import json
from collections.abc import AsyncGenerator

import httpx

from app.config import settings

_BASE = settings.routerai_base_url.rstrip("/")
_HEADERS = {
    "Authorization": f"Bearer {settings.routerai_api_key}",
    "Content-Type": "application/json",
}
_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


async def create_embeddings(texts: list[str]) -> list[list[float]]:
    """Batch-embed texts. Returns one vector per input text."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            f"{_BASE}/embeddings",
            headers=_HEADERS,
            json={
                "model": settings.routerai_embedding_model,
                "input": texts,
            },
        )
        resp.raise_for_status()
        data = resp.json()
    # Sort by index to guarantee order matches input
    items = sorted(data["data"], key=lambda d: d["index"])
    return [item["embedding"] for item in items]


async def chat_completion_stream(
    messages: list[dict],
    model: str | None = None,
) -> AsyncGenerator[str]:
    """Yield content deltas from a streaming chat completion."""
    model = model or settings.routerai_llm_model
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        async with client.stream(
            "POST",
            f"{_BASE}/chat/completions",
            headers=_HEADERS,
            json={
                "model": model,
                "messages": messages,
                "stream": True,
            },
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line.removeprefix("data: ").strip()
                if payload == "[DONE]":
                    break
                chunk = json.loads(payload)
                delta = chunk["choices"][0].get("delta", {})
                content = delta.get("content")
                if content:
                    yield content
