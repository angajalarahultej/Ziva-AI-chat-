"""Local Whisper via faster-whisper. Free, no key, handles en + te + code-switch.
Falls back to stub mode if the package/model isn't installed so the app still runs."""
import asyncio
import re
from app.core.config import settings
from app.core.logging import get_logger
from app.services.stt.base import STTProvider

log = get_logger("stt.whisper")
_model = None

_DEV_RE = re.compile(r"[\u0900-\u097f]+")
_TAMIL_RE = re.compile(r"[\u0b80-\u0bff]+")
# Scripts we accept from the mic: Latin, Telugu, Devanagari (+ digits/punct).
# Anything else (Tamil/Arabic/CJK/Thai…) is a noise hallucination — reject it
# instead of answering garbage.
_FORBIDDEN_RE = re.compile(
    r"[\u0b80-\u0bff\u0600-\u06ff\u0e00-\u0e7f\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")
_REPEAT_RE = re.compile(r"(\b\w+\b)(?:\s+\1){3,}", re.IGNORECASE)


def _to_telugu_script(text: str) -> str:
    """Whisper-small often hears Telugu correctly but writes it in Devanagari
    (sometimes Tamil). When detection says Telugu, transliterate back —
    both are Brahmic scripts with near 1:1 mapping. Latin passes through."""
    try:
        from indic_transliteration import sanscript
        from indic_transliteration.sanscript import transliterate
    except ImportError:
        return text
    try:
        text = _DEV_RE.sub(
            lambda m: transliterate(m.group(0), sanscript.DEVANAGARI, sanscript.TELUGU), text)
        text = _TAMIL_RE.sub(
            lambda m: transliterate(m.group(0), sanscript.TAMIL, sanscript.TELUGU), text)
    except Exception as e:
        log.warning(f"transliteration skipped: {e}")
    return text


class WhisperSTT(STTProvider):
    def _load(self):
        global _model
        if _model is None:
            from faster_whisper import WhisperModel
            device = "cpu" if settings.STT_DEVICE == "auto" else settings.STT_DEVICE
            log.info(f"loading whisper model={settings.STT_MODEL_SIZE} device={device}")
            _model = WhisperModel(settings.STT_MODEL_SIZE, device=device,
                                  compute_type="int8", cpu_threads=2)
        return _model

    async def transcribe(self, audio_path: str, language_hint: str = "auto") -> str:
        model = self._load()
        # Blocking C++ inference MUST run in a thread — otherwise the entire
        # server (health checks, new turns, other requests) freezes mid-STT.
        segments, info = await asyncio.to_thread(
            model.transcribe,
            audio_path, beam_size=5, vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            condition_on_previous_text=False,
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
            no_speech_threshold=0.6,
        )
        segs = list(segments)
        text = "".join(s.text for s in segs).strip()
        detected = getattr(info, "language", "") or ""
        log.info(f"stt detected={detected}")
        if detected == "te":
            text = _to_telugu_script(text)
        self._reject_garbage(text, segs, detected)
        return text

    @staticmethod
    def _reject_garbage(text: str, segs, detected: str = "") -> None:
        """Raise instead of letting noise-hallucinations reach the LLM."""
        if not text:
            raise RuntimeError("Could not hear you — please try again.")
        # 0. Detected language outside en/te/hi (e.g. Japanese/Portuguese on
        #    pure noise) can only be a hallucination — we don't speak it.
        if detected and detected not in ("en", "te", "hi"):
            raise RuntimeError("Could not catch that clearly — please say that again.")
        # 1. Low model confidence → probably bikes/fans, not speech.
        total = sum(len(s.text) for s in segs) or 1
        avg_lp = sum(s.avg_logprob * len(s.text) for s in segs) / total
        if avg_lp < -0.8:
            raise RuntimeError("Too much background noise — please speak closer to the mic.")
        # 2. Hallucination loops ("thanks thanks thanks thanks").
        if _REPEAT_RE.search(text):
            raise RuntimeError("Could not hear you clearly — please say that again.")
        # 3. Wrong-script output (Tamil/Arabic/CJK…) — not our languages.
        if _FORBIDDEN_RE.search(text):
            raise RuntimeError("Could not catch that clearly — please say that again.")
