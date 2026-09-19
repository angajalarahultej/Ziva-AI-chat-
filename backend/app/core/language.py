"""Heuristic language detection: en / te / hi / mixed. No external dependency."""
import re

_TELUGU_RE = re.compile(r"[\u0c00-\u0c7f]")
_DEVANAGARI_RE = re.compile(r"[\u0900-\u097f]")
# Common Romanized Telugu markers
_TE_ROMAN = {
    "nenu", "nenu", "naku", "naaku", "neenu", "nen", "emi", "enti", "ela",
    "cheyyi", "cheppu", "cheppara", "kavali", "leda", "aithe", "inka",
    "chala", "ga", "lo", "ki", "ni", "gurinchi", "gurunchi", "ante",
    "unnanu", "unna", "undi", "unnayi", "elaunnaru", "bagunnara",
    "telugu", "ardham", "simple", "tired", "ivala", "repu", "nuvvu",
}


def detect_language(text: str, preference: str = "AUTO") -> str:
    """Return 'te' | 'en' | 'hi' | 'mixed'."""
    pref = (preference or "AUTO").upper()
    if pref in ("ENGLISH", "EN"):
        return "en"
    if pref in ("TELUGU", "TE"):
        return "te"
    if pref in ("HINDI", "HI"):
        return "hi"

    t = text or ""
    has_te = bool(_TELUGU_RE.search(t))
    has_hi = bool(_DEVANAGARI_RE.search(t))
    words = set(re.findall(r"[a-zA-Z]+", t.lower()))
    roman_te = len(words & _TE_ROMAN) >= 1

    if has_te and has_hi:
        return "mixed"
    if has_te:
        return "te" if not words else "mixed"
    if has_hi:
        return "hi" if not words else "mixed"
    if roman_te and words:
        # Romanized Telugu mixed with English, or pure Roman Telugu
        english_common = {"the", "is", "are", "what", "how", "can", "you", "please", "explain"}
        if words & english_common:
            return "mixed"
        return "te"
    return "en"


_TAMIL_RE = re.compile(r"[\u0b80-\u0bff]")
_ARABIC_RE = re.compile(r"[\u0600-\u06ff]")
_OTHER_INDIC_RE = re.compile(r"[\u0b80-\u0bff\u0600-\u06ff\u0e00-\u0e7f\u4e00-\u9fff\u3040-\u30ff]")


def reply_script_ok(snippet: str, user_text: str, lang: str) -> bool:
    """Guardrail for weak models: does the reply use the script the user used?
    en → Latin only. te (Telugu script in) → must contain Telugu script.
    te (Roman in) / mixed → Latin and/or Telugu, nothing else.
    hi → Devanagari (or Latin if user typed Roman). Anything else → reject."""
    s = snippet or ""
    u = user_text or ""
    has_te = bool(_TELUGU_RE.search(s))
    has_hi = bool(_DEVANAGARI_RE.search(s))
    has_other = bool(_OTHER_INDIC_RE.search(s))
    if has_other:
        return False
    if lang == "en":
        return not has_te and not has_hi
    if lang == "hi":
        if _DEVANAGARI_RE.search(u):
            return has_hi
        return not has_te
    if lang == "te":
        if _TELUGU_RE.search(u):
            return has_te
        return not has_hi  # Roman Telugu in: Latin or Telugu reply both fine
    return not has_other  # mixed: Latin + Telugu ok
