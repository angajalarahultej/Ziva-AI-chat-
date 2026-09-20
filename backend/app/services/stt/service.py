"""Replaceable STT service. Uses local Whisper when available, else stub."""
import asyncio
import time
from pathlib import Path
from app.core.config import settings
from app.core.logging import get_logger
from app.services.stt.denoise import denoise_to_wav

log = get_logger("stt.service")


class STTService:
    def __init__(self) -> None:
        self._provider = None
        self._available: bool | None = None

    def _ensure(self):
        if self._provider is None:
            try:
                import faster_whisper  # noqa: F401
                from app.services.stt.whisper_stt import WhisperSTT
                self._provider = WhisperSTT()
                self._available = True
            except Exception as e:
                log.warning(f"whisper unavailable, STT running in stub mode: {e}")
                self._provider = None
                self._available = False
        return self._provider

    @property
    def available(self) -> bool:
        self._ensure()
        return bool(self._available)

    async def transcribe(self, audio_path: str) -> tuple[str, float]:
        t0 = time.perf_counter()
        provider = self._ensure()
        if provider is None:
            raise RuntimeError("STT engine not installed. Run: pip install faster-whisper")
        # Denoise first (bike/fan/hum) unless disabled for speed — then raw.
        if settings.STT_DENOISE:
            clean_path = await asyncio.to_thread(denoise_to_wav, audio_path)
        else:
            clean_path = audio_path
        try:
            text = await provider.transcribe(clean_path)
        finally:
            if clean_path != audio_path:
                Path(clean_path).unlink(missing_ok=True)
        secs = time.perf_counter() - t0
        log.info(f"stt done chars={len(text)} secs={secs:.2f}")
        return text, secs


stt_service = STTService()
