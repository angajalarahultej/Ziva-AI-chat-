"""Edge-TTS provider. Free, no API key, strong en-IN + te-IN voices."""
import edge_tts
from app.core.config import settings
from app.services.tts.base import TTSProvider

_VOICES = {
    # Sweet Indian female (same Microsoft family Narakeet uses) + male option.
    "Female": {"en": settings.TTS_VOICE_EN, "te": settings.TTS_VOICE_TE,
               "hi": settings.TTS_VOICE_HI, "mixed": settings.TTS_VOICE_TE},
    "Male": {"en": "en-IN-PrabhatNeural", "te": "te-IN-MohanBabuNeural",
             "hi": "hi-IN-ArjunNeural", "mixed": "te-IN-MohanBabuNeural"},
}


class EdgeTTSProvider(TTSProvider):
    async def synthesize(self, text: str, language: str, out_path: str,
                         voice_name: str = "Female") -> str:
        voices = _VOICES.get(voice_name, _VOICES["Female"])
        voice = voices.get(language, voices["en"])
        tts = edge_tts.Communicate(text, voice, rate=settings.TTS_RATE, volume=settings.TTS_VOLUME)
        await tts.save(out_path)
        return out_path
