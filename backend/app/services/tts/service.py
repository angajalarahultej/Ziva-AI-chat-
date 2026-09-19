"""Replaceable TTS service. Edge-TTS when installed; else text-only (browser speaks)."""
import re
import time
import uuid
from pathlib import Path
from app.core.logging import get_logger

log = get_logger("tts.service")
ASTRA_ROOT = Path(__file__).resolve().parents[4]  # astra/
AUDIO_DIR = ASTRA_ROOT / "data" / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE00-\uFE0F]", flags=re.UNICODE)
_MD_RE = re.compile(r"[*_#`>|~]+")


def clean_for_speech(text: str) -> str:
    """Strip markdown/emoji/URLs so TTS doesn't read 'asterisk asterisk' aloud."""
    t = _EMOJI_RE.sub("", text or "")
    t = re.sub(r"https?://\S+", "link", t)
    t = _MD_RE.sub("", t)
    t = re.sub(r"\n{2,}", ". ", t).replace("\n", " ")
    return re.sub(r"\s{2,}", " ", t).strip()


_SENT_END = re.compile(r"(?<=[.!?।])\s+")


def split_sentences(buffer: str) -> tuple[list[str], str]:
    """Pull complete sentences off buffer; return (sentences, remainder)."""
    parts = _SENT_END.split(buffer)
    if len(parts) == 1:
        return [], buffer
    return [p.strip() for p in parts[:-1] if p.strip()], parts[-1]


class TTSService:
    def __init__(self) -> None:
        self._providers: dict[str, object] = {}
        self._broken: set[str] = set()  # circuit breaker per provider
        self._order = ["google", "edge"]

    def _get(self, name: str):
        if name in self._broken:
            return None
        if name not in self._providers:
            try:
                if name == "google":
                    from app.services.tts.google_tts import GoogleTTSProvider
                    self._providers[name] = GoogleTTSProvider()
                elif name == "edge":
                    import edge_tts  # noqa: F401
                    from app.services.tts.edge_tts import EdgeTTSProvider
                    self._providers[name] = EdgeTTSProvider()
                else:
                    return None
            except Exception as e:
                log.warning(f"tts provider {name} unavailable: {e}")
                self._broken.add(name)
                return None
        return self._providers.get(name)

    def _ensure(self):
        for name in self._order:
            p = self._get(name)
            if p is not None:
                return p
        return None

    @property
    def available(self) -> bool:
        return self._ensure() is not None

    async def synthesize(self, text: str, language: str) -> tuple[str | None, float]:
        """Returns (audio_url_or_None, secs). None => frontend uses browser speech.
        Tries providers in order; a failing provider is broken-circuited."""
        t0 = time.perf_counter()
        for name in self._order:
            provider = self._get(name)
            if provider is None:
                continue
            try:
                fname = f"{uuid.uuid4()}.mp3"
                out = str(AUDIO_DIR / fname)
                await provider.synthesize(text, language, out)
                secs = time.perf_counter() - t0
                log.info(f"tts done via={name} lang={language} chars={len(text)} secs={secs:.2f}")
                return f"/audio/{fname}", secs
            except Exception as e:
                log.warning(f"tts provider {name} failed, breaking circuit: {e}")
                self._broken.add(name)
                continue
        return None, 0.0


tts_service = TTSService()
