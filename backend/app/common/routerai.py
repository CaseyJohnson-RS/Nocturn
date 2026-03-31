"""Thin async client for the RouterAI OpenAI-compatible API."""

import json
from collections.abc import AsyncGenerator

import httpx

from app.config import settings

def _build_base_url() -> str:
    return settings.routerai_base_url.rstrip("/")

_HEADERS = {
    "Authorization": f"Bearer {settings.routerai_api_key}",
    "Content-Type": "application/json",
}
_TIMEOUT = httpx.Timeout(60.0, connect=10.0)
_MODEL_CONTEXT_CACHE: dict[str, int] = {}


async def create_embeddings(texts: list[str]) -> list[list[float]]:
    """Batch-embed texts. Returns one vector per input text."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            f"{_build_base_url()}/embeddings",
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


async def get_model_context_length(model: str) -> int | None:
    """Return the context window size for a model, if available."""
    if not model:
        return None
    if model in _MODEL_CONTEXT_CACHE:
        return _MODEL_CONTEXT_CACHE[model]

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(f"{_build_base_url()}/models", headers=_HEADERS)
        resp.raise_for_status()
        data = resp.json()

    models: list[dict] = []
    if isinstance(data, dict):
        models = data.get("data", [])
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                models.extend(item.get("data", []))

    for item in models:
        if item.get("id") == model:
            context_length = item.get("context_length")
            if isinstance(context_length, int):
                _MODEL_CONTEXT_CACHE[model] = context_length
                return context_length
    return None


async def chat_completion_stream(
    messages: list[dict],
    model: str | None = None,
) -> AsyncGenerator[str]:
    """Yield content deltas from a streaming chat completion."""
    model = model or settings.routerai_llm_model
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        async with client.stream(
            "POST",
            f"{_build_base_url()}/chat/completions",
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
