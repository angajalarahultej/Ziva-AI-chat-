"""LLMService with configurable primary + fallback. No model hardcoded outside .env."""
import time
from collections.abc import AsyncIterator
from app.core.config import settings
from app.core.logging import get_logger
from app.services.llm.ollama import OllamaProvider
from app.services.llm.openrouter import OpenRouterProvider

log = get_logger("llm.service")


def _chain() -> list[tuple[object, str]]:
    """Ordered (provider, model): primary per LLM_PROVIDER, then the fallback,
    then the local model as a last resort (offline, no quota)."""
    if settings.LLM_PROVIDER == "ollama":
        chain = [(OllamaProvider(), settings.LLM_LOCAL_MODEL)]
    else:
        chain = [(OpenRouterProvider(), settings.LLM_MODEL)]
    chain.append((OpenRouterProvider(), settings.LLM_FALLBACK_MODEL))
    if not any(isinstance(p, OllamaProvider) for p, _ in chain):
        chain.append((OllamaProvider(), settings.LLM_LOCAL_MODEL))
    return chain


class LLMService:
    async def chat(self, messages: list[dict]) -> tuple[str, str]:
        """Returns (reply, model_used). Tries each link in the chain in order."""
        t0 = time.perf_counter()
        last_err: Exception | None = None
        for provider, model in _chain():
            try:
                reply = await provider.chat(messages, model=model)
                log.info(f"llm ok model={model} secs={time.perf_counter()-t0:.2f}")
                return reply, model
            except Exception as e:
                log.warning(f"llm {model} failed: {e}")
                last_err = e
        log.error(f"all llms failed: {last_err}")
        raise RuntimeError(
            "AI core unavailable. Check your key in astra/.env (OPENROUTER_API_KEY) "
            "and that the configured free model still exists."
        )

    async def chat_stream(self, messages: list[dict]) -> AsyncIterator[tuple[str, str]]:
        """Yield (delta, model_used). Falls to the next link ONLY if the current
        one fails before producing any token — mid-stream failures end the stream."""
        t0 = time.perf_counter()
        for provider, model in _chain():
            got_any = False
            try:
                async for delta in provider.chat_stream(messages, model=model):
                    if not got_any:
                        got_any = True
                        log.info(f"llm first-token model={model} secs={time.perf_counter()-t0:.2f}")
                    yield delta, model
                return
            except Exception as e:
                if got_any:
                    log.warning(f"{model} died mid-stream, keeping partial: {e}")
                    return
                log.warning(f"llm {model} failed, trying next: {e}")
        raise RuntimeError(
            "AI core unavailable. Check your key in astra/.env (OPENROUTER_API_KEY) "
            "and that the configured free model still exists."
        )


llm_service = LLMService()
