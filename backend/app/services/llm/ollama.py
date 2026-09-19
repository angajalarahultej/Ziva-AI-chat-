"""Ollama local-model provider. No key, no quota, works offline.
Install: https://ollama.com/download  then e.g. `ollama pull gemma3:4b`."""
import json
from collections.abc import AsyncIterator
import httpx
from app.core.config import settings
from app.services.llm.base import LLMProvider


class OllamaProvider(LLMProvider):
    async def chat(self, messages: list[dict], model: str | None = None) -> str:
        use_model = model or settings.LLM_LOCAL_MODEL
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.post(
                    f"{settings.LLM_LOCAL_URL}/api/chat",
                    json={"model": use_model, "messages": messages, "stream": False,
                          "options": {"temperature": settings.LLM_TEMPERATURE,
                                      "num_predict": settings.LLM_MAX_TOKENS}},
                )
                r.raise_for_status()
                return r.json()["message"]["content"]
        except httpx.ConnectError:
            raise RuntimeError(
                f"Cannot reach Ollama at {settings.LLM_LOCAL_URL} — "
                "is Ollama installed and running (`ollama serve`)?")

    async def chat_stream(self, messages: list[dict],
                          model: str | None = None) -> AsyncIterator[str]:
        use_model = model or settings.LLM_LOCAL_MODEL
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream(
                    "POST", f"{settings.LLM_LOCAL_URL}/api/chat",
                    json={"model": use_model, "messages": messages, "stream": True,
                          "options": {"temperature": settings.LLM_TEMPERATURE,
                                      "num_predict": settings.LLM_MAX_TOKENS}},
                ) as r:
                    r.raise_for_status()
                    async for line in r.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            chunk = json.loads(line)["message"].get("content", "")
                        except (json.JSONDecodeError, KeyError):
                            continue
                        if chunk:
                            yield chunk
        except httpx.ConnectError:
            raise RuntimeError(
                f"Cannot reach Ollama at {settings.LLM_LOCAL_URL} — "
                "is Ollama installed and running (`ollama serve`)?")
