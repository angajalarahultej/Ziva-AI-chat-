"""Google Translate TTS provider. Free, no API key, supports te/en/hi.
Unofficial endpoint — kept behind the TTSProvider interface so it can be
swapped without touching the rest of the app."""
import os
import re
import subprocess
import httpx
from app.services.tts.base import TTSProvider

_ENDPOINT = "https://translate.google.com/translate_tts"
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
_LANG = {"en": "en", "te": "te", "hi": "hi", "mixed": "te"}
# Livelier delivery: pitch-preserving speedup (same female voice, less drawl).
SPEED = 1.15


def _chunks(text: str, limit: int = 180) -> list[str]:
    words, cur, out = text.split(), "", []
    for w in words:
        if len(cur) + len(w) + 1 > limit:
            out.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        out.append(cur)
    return out or [text]


class GoogleTTSProvider(TTSProvider):
    async def synthesize(self, text: str, language: str, out_path: str,
                         voice_name: str = "Female") -> str:
        tl = _LANG.get(language, "en")
        parts: list[bytes] = []
        async with httpx.AsyncClient(timeout=30, headers={"User-Agent": _UA}) as client:
            for ch in _chunks(text):
                r = await client.get(_ENDPOINT, params={
                    "ie": "UTF-8", "client": "tw-ob", "tl": tl, "q": ch})
                r.raise_for_status()
                c = r.content
                is_mp3 = c.startswith(b"ID3") or (
                    len(c) > 2 and c[0] == 0xFF and (c[1] & 0xE0) == 0xE0)
                if not is_mp3:
                    raise RuntimeError(f"unexpected TTS payload for tl={tl}")
                parts.append(c)
        with open(out_path, "wb") as f:
            for p in parts:
                f.write(p)
        _speed_up(out_path)
        return out_path


def _speed_up(path: str) -> None:
    """atempo keeps pitch (same sweet female voice), just less slow."""
    try:
        tmp = path + ".fast.mp3"
        r = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", path,
             "-filter:a", f"atempo={SPEED}", tmp],
            timeout=20)
        if r.returncode == 0:
            os.replace(tmp, path)
    except Exception:
        pass  # original speed is fine, don't break speech over this
