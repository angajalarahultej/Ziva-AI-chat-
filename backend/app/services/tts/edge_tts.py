"""Edge-TTS provider. Free, no API key, strong en-IN + te-IN voices."""
import edge_tts
from app.core.config import settings
from app.services.tts.base import TTSProvider

_VOICE = {"en": settings.TTS_VOICE_EN, "te": settings.TTS_VOICE_TE, "hi": settings.TTS_VOICE_HI}


class EdgeTTSProvider(TTSProvider):
    async def synthesize(self, text: str, language: str, out_path: str) -> str:
        voice = _VOICE.get(language, _VOICE["en"])
        if language == "mixed":
            voice = _VOICE["te"]  # Telugu voice handles code-switch naturally
        tts = edge_tts.Communicate(text, voice, rate=settings.TTS_RATE, volume=settings.TTS_VOLUME)
        await tts.save(out_path)
        return out_path
