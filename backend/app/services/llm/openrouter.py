"""OpenRouter-compatible chat provider. Model name fully configurable via .env."""
import json
from collections.abc import AsyncIterator
import httpx
from app.core.config import settings
from app.core.logging import get_logger
from app.services.llm.base import LLMProvider

log = get_logger("llm.openrouter")

_FRIENDLY = {
    401: "OpenRouter key rejected (401) — check OPENROUTER_API_KEY in astra/.env",
    404: "model not found (404) — pick a live :free model in astra/.env",
    429: "Free-model rate limit hit (429) — wait a minute and try again",
}


def _friendly(code: int, model: str) -> str:
    base = _FRIENDLY.get(code, f"LLM provider error ({code}) — try again shortly")
    return f"{base} [model={model}]"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "HTTP-Referer": settings.OPENROUTER_HTTP_REFERER,
        "X-Title": settings.OPENROUTER_APP_TITLE,
    }


class OpenRouterProvider(LLMProvider):
    async def chat(self, messages: list[dict], model: str | None = None) -> str:
        if not settings.OPENROUTER_API_KEY:
            raise RuntimeError("OPENROUTER_API_KEY is empty — add your free-model key to astra/.env")
        use_model = model or settings.LLM_MODEL
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(
                    f"{settings.OPENROUTER_BASE_URL}/chat/completions",
                    headers=_headers(),
                    json={"model": use_model, "messages": messages,
                          "max_tokens": settings.LLM_MAX_TOKENS,
                          "temperature": settings.LLM_TEMPERATURE},
                )
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            raise RuntimeError(_friendly(e.response.status_code, use_model))

    async def chat_stream(self, messages: list[dict],
                          model: str | None = None) -> AsyncIterator[str]:
        """Yield text deltas as they arrive. Raises BEFORE any yield on HTTP errors
        so the caller can fall back to another model cleanly."""
        if not settings.OPENROUTER_API_KEY:
            raise RuntimeError("OPENROUTER_API_KEY is empty — add your free-model key to astra/.env")
        use_model = model or settings.LLM_MODEL
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                async with client.stream(
                    "POST",
                    f"{settings.OPENROUTER_BASE_URL}/chat/completions",
                    headers=_headers(),
                    json={"model": use_model, "messages": messages,
                          "max_tokens": settings.LLM_MAX_TOKENS,
                          "temperature": settings.LLM_TEMPERATURE,
                          "stream": True},
                ) as r:
                    r.raise_for_status()
                    async for line in r.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        payload = line[5:].strip()
                        if not payload or payload == "[DONE]":
                            continue
                        try:
                            delta = json.loads(payload)["choices"][0]["delta"].get("content", "")
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
                        if delta:
                            yield delta
        except httpx.HTTPStatusError as e:
            raise RuntimeError(_friendly(e.response.status_code, use_model))
