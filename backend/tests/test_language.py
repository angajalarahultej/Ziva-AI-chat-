from app.core.language import detect_language, reply_script_ok


def test_telugu_script():
    assert detect_language("హాయ్ ఆస్ట్రా, నువ్వు ఎలా ఉన్నావు?") == "te"


def test_english():
    assert detect_language("Can you explain Python classes?") == "en"


def test_roman_telugu_mixed():
    assert detect_language("Naku Python gurinchi simple ga explain cheyyi.") == "mixed"


def test_preference_override():
    assert detect_language("hello", "TELUGU") == "te"


def test_script_ok_english():
    assert reply_script_ok("I am doing well, thank you!", "how are you", "en") is True
    assert reply_script_ok("బాగున్నాను!", "how are you", "en") is False


def test_script_ok_telugu():
    assert reply_script_ok("నేను బాగున్నాను!", "నువ్వు ఎలా ఉన్నావు?", "te") is True
    assert reply_script_ok("I am fine.", "నువ్వు ఎలా ఉన్నావు?", "te") is False
    # Roman Telugu in: Latin reply acceptable
    assert reply_script_ok("Nenu bagunnanu.", "nenu ela unnanu", "te") is True


def test_script_ok_rejects_other_scripts():
    assert reply_script_ok("நன்றி!", "how are you", "en") is False
    assert reply_script_ok("ہیلو", "how are you", "mixed") is False


def test_garbage_rejection():
    from app.services.stt.whisper_stt import WhisperSTT
    import pytest

    class Seg:
        def __init__(self, text, lp):
            self.text = text
            self.avg_logprob = lp

    # hallucination loop
    with pytest.raises(RuntimeError):
        WhisperSTT._reject_garbage("thanks thanks thanks thanks", [Seg("thanks thanks thanks thanks", -0.2)], "en")
    # wrong language hallucination
    with pytest.raises(RuntimeError):
        WhisperSTT._reject_garbage("ご視聴ありがとうございました", [Seg("x", -0.3)], "ja")
    # low confidence noise
    with pytest.raises(RuntimeError):
        WhisperSTT._reject_garbage("mumble", [Seg("mumble", -1.5)], "en")
    # genuine speech passes
    WhisperSTT._reject_garbage("నేను బాగున్నాను", [Seg("నేను బాగున్నాను", -0.4)], "te")
