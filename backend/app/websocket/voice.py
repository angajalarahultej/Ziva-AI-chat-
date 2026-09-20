"""Real-time voice loop: audio_chunk → STT → streamed LLM → sentence-chunked TTS.

Perceived latency = time-to-first-token (~1s) + first sentence TTS, NOT the full
reply. Sentences are synthesized and played as they arrive.

Barge-in: client sending `interrupt` sets a per-connection flag; the pending
turn is abandoned and the socket returns to LISTENING.
"""
import asyncio
import base64
import tempfile
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from app.core.language import detect_language
from app.core.logging import get_logger
from app.db.database import SessionLocal, init_db
from app.models.db_models import Conversation
from app.services.conversation.manager import manager
from app.services.stt.service import stt_service
from app.services.tts.service import AUDIO_DIR, clean_for_speech, split_sentences, tts_service

log = get_logger("ws.voice")
router = APIRouter()


@router.websocket("/ws/voice")
async def voice_socket(ws: WebSocket):
    # Private-Network opt-in on the 101 handshake so public-https pages
    # (Vercel) may open this localhost socket in Chrome.
    # NOTE: starlette wants raw byte-tuples here, not a str dict.
    await ws.accept(headers=[(b"access-control-allow-private-network", b"true")])
    init_db()
    db: Session = SessionLocal()
    conversation_id: str | None = None
    lang_pref = "AUTO"
    voice_mode = "server"  # or "browser": client speaks text itself, skip synth
    voice_name = "Female"  # or "Male": speaker option from the client
    interrupted = False
    current: asyncio.Task | None = None

    def launch(coro) -> None:
        """Start a turn, cancelling any older one — only the LATEST question
        ever gets answered, never one-by-one through a backlog."""
        nonlocal current, interrupted
        if current is not None and not current.done():
            current.cancel()
        interrupted = False
        current = asyncio.create_task(coro)

    async def run_turn(text: str) -> None:
        nonlocal conversation_id
        try:
            conversation_id = await _handle_text(
                ws, db, text, lang_pref, conversation_id,
                lambda: interrupted, voice_mode, voice_name)
        except asyncio.CancelledError:
            # Superseded by a newer question — the new turn owns the UI now.
            return

    try:
        await ws.send_json({"event": "state_change", "state": "ONLINE"})
        while True:
            msg = await ws.receive_json()
            kind = msg.get("event")

            if kind == "config":
                lang_pref = msg.get("language_preference", "AUTO")
                conversation_id = msg.get("conversation_id") or conversation_id
                if msg.get("voice") in ("browser", "server"):
                    voice_mode = msg.get("voice")
                if msg.get("voice_name") in ("Female", "Male"):
                    voice_name = msg.get("voice_name")
                await ws.send_json({"event": "state_change", "state": "LISTENING"})
                continue

            if kind == "interrupt":
                interrupted = True
                if current is not None and not current.done():
                    current.cancel()
                await ws.send_json({"event": "state_change", "state": "INTERRUPTED"})
                await ws.send_json({"event": "state_change", "state": "LISTENING"})
                continue

            if kind == "text_message":
                launch(run_turn(msg.get("text", "")))
                continue

            if kind == "audio_chunk":
                launch(_voice_turn(ws, db, msg, lang_pref, conversation_id,
                                   lambda: interrupted, voice_mode, voice_name, run_turn))
                continue
    except WebSocketDisconnect:
        log.info("voice client disconnected")
    finally:
        if current is not None and not current.done():
            current.cancel()
        db.close()


async def _voice_turn(ws: WebSocket, db: Session, msg: dict, lang_pref: str,
                    conversation_id: str | None, is_interrupted,
                    voice_mode: str, voice_name: str, run_turn) -> None:
    """One audio turn: transcribe, then answer — unless a newer turn cancels us."""
    await ws.send_json({"event": "state_change", "state": "PROCESSING"})
    try:
        text = await _transcribe_chunk(msg)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        await ws.send_json({"event": "error", "message": str(e)})
        await ws.send_json({"event": "state_change", "state": "LISTENING"})
        return
    await ws.send_json({"event": "transcription", "text": text})
    await run_turn(text)


async def _transcribe_chunk(msg: dict) -> str:
    raw = base64.b64decode(msg.get("audio_b64", ""))
    if len(raw) < 500:
        raise RuntimeError("Audio too short — hold the mic button while speaking.")
    if len(raw) > 1_500_000:
        raise RuntimeError("That was too long — keep each turn under ~30 seconds.")
    suffix = ".webm" if "webm" in str(msg.get("mime", "")) else ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(raw)
        path = f.name
    try:
        # Fast duration probe — reject overlong clips BEFORE the slow STT.
        try:
            import av
            with av.open(path) as container:
                if container.duration and container.duration > 35_000_000:
                    raise RuntimeError("That was too long — keep each turn under ~30 seconds.")
        except RuntimeError:
            raise
        except Exception:
            pass  # probe failed; let STT decide
        text, _ = await stt_service.transcribe(path)
    finally:
        Path(path).unlink(missing_ok=True)
    if not text.strip():
        raise RuntimeError("Could not hear you — please try again.")
    return text


def _resolved(value: tuple[str | None, str]) -> asyncio.Future:
    """Pre-completed future that quacks like a finished synth Task."""
    fut = asyncio.get_running_loop().create_future()
    fut.set_result(value)
    return fut


async def _synth_one(sentence: str, lang: str, voice_name: str = "Female") -> tuple[str | None, str]:
    """Synthesize + base64 in memory; temp file deleted at once. Returns (b64, clean)."""
    clean = clean_for_speech(sentence)
    if not clean:
        return None, ""
    try:
        audio_url, _ = await tts_service.synthesize(clean, lang, voice_name)
        if audio_url:
            fpath = AUDIO_DIR / Path(audio_url).name
            data = fpath.read_bytes()
            fpath.unlink(missing_ok=True)
            return base64.b64encode(data).decode(), clean
    except Exception as e:
        log.warning(f"tts failed, text-only: {e}")
    return None, clean


async def _handle_text(ws: WebSocket, db: Session, text: str, lang_pref: str,
                       conversation_id: str | None, is_interrupted,
                       voice_mode: str = "server",
                       voice_name: str = "Female") -> str | None:
    conv = None
    if conversation_id:
        conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if conv is None:
        conv = Conversation(title=(text[:40] or "Voice conversation"))
        db.add(conv)
        db.commit()
        db.refresh(conv)
        await ws.send_json({"event": "config", "conversation_id": conv.id})
    await ws.send_json({"event": "user_message", "text": text})
    lang = detect_language(text, lang_pref)
    buf = ""
    sent_index = 0
    speaking = False
    # Ordered concurrent TTS: sentences synthesize in parallel (up to 3 at a
    # time) but are always SENT in order, so playback has no synth gaps.
    pending: dict[int, asyncio.Task] = {}
    next_emit = 0
    sem = asyncio.Semaphore(3)

    async def emit_ready() -> None:
        nonlocal next_emit
        while next_emit in pending and pending[next_emit].done():
            idx = next_emit
            audio_b64, clean = pending.pop(idx).result()
            next_emit += 1
            if not clean:
                continue
            await ws.send_json({"event": "assistant_audio", "audio_url": None,
                                "audio_b64": audio_b64, "text": clean,
                                "language": lang, "index": idx, "final": False})

    def submit(sentence: str) -> None:
        nonlocal sent_index
        idx = sent_index
        sent_index += 1
        if voice_mode == "browser":
            # Instant path: client speaks the text itself — no synth, no wait.
            clean = clean_for_speech(sentence)
            if clean:
                pending[idx] = _resolved((None, clean))
            return

        async def _run() -> tuple[str | None, str]:
            async with sem:
                return await _synth_one(sentence, lang, voice_name)

        pending[idx] = asyncio.create_task(_run())

    async def drain() -> None:
        if pending:
            await asyncio.wait(pending.values())
            await emit_ready()

    async def cancel_pending() -> None:
        for t in pending.values():
            t.cancel()
        pending.clear()

    try:
        async for kind, payload in manager.reply_stream(db, conv, text, lang_pref):
            if is_interrupted():
                await cancel_pending()
                return conv.id  # user barged in — drop this turn
            if kind == "token":
                if not speaking:
                    speaking = True
                    await ws.send_json({"event": "state_change", "state": "SPEAKING"})
                    await ws.send_json({"event": "assistant_text", "text": "",
                                        "language": lang, "partial": True})
                await ws.send_json({"event": "assistant_text_delta", "delta": payload})
                buf += str(payload)
                sentences, buf = split_sentences(buf)
                for s in sentences:
                    submit(s)
                await emit_ready()
            elif kind == "done":
                result = payload
                rest = clean_for_speech(buf)
                if rest:
                    submit(rest)
                await drain()
                conv.updated_at = datetime.utcnow()
                db.commit()
                await ws.send_json({"event": "assistant_text",
                                    "text": result["reply"], "language": result["language"],
                                    "model": result["model"], "partial": False})
                await ws.send_json({"event": "assistant_audio", "audio_url": None,
                                    "text": "", "language": lang, "final": True})
    except asyncio.CancelledError:
        await cancel_pending()
        raise
    except Exception as e:
        await cancel_pending()
        await ws.send_json({"event": "error", "message": str(e)})
    await ws.send_json({"event": "state_change", "state": "LISTENING"})
    return conv.id
