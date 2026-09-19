"""ConversationManager: transcript → language → short-term + long-term + knowledge → LLM → save."""
from collections.abc import AsyncIterator
from sqlalchemy.orm import Session
from app.core.language import detect_language, reply_script_ok
from app.core.logging import get_logger
from app.models.db_models import Conversation
from app.services.conversation import prompts
from app.services.knowledge.store import retrieve as kb_retrieve
from app.services.llm.service import llm_service
from app.services.memory import long_term, short_term
from app.services.tts.service import split_sentences

log = get_logger("conversation")

_CORRECTION = ("SYSTEM CORRECTION: you replied in the wrong language/script. "
               "The user wrote in {label}. Reply again using ONLY that language and script, "
               "plain speakable text.")


class ConversationManager:
    def _context(self, db: Session, conversation: Conversation,
                 user_text: str, language_preference: str = "AUTO") -> tuple[str, list[dict]]:
        lang = detect_language(user_text, language_preference)
        log.info(f"lang={lang} conv={conversation.id} chars={len(user_text)}")
        short_term.save_message(db, conversation.id, "user", user_text, lang)
        history = short_term.recent_messages(db, conversation.id)
        memories = long_term.search(db, conversation.user_id, user_text)
        kb = kb_retrieve(db, user_text)
        messages = prompts.build_messages(user_text, lang, history, memories, kb)
        return lang, messages

    def _finish(self, db: Session, conversation: Conversation,
                reply_text: str, lang: str, model: str, user_text: str) -> dict:
        short_term.save_message(db, conversation.id, "assistant", reply_text, lang)
        saved_mem = long_term.save_if_useful(db, conversation.user_id, user_text)
        return {"reply": reply_text, "language": lang, "model": model,
                "memory_saved": saved_mem is not None}

    async def reply(self, db: Session, conversation: Conversation,
                    user_text: str, language_preference: str = "AUTO") -> dict:
        lang, messages = self._context(db, conversation, user_text, language_preference)
        reply_text, model = await llm_service.chat(messages)
        if not reply_script_ok(reply_text, user_text, lang):
            log.warning("reply wrong script, retrying with correction (non-stream)")
            messages = [*messages, {"role": "user", "content": _CORRECTION.format(label=lang)}]
            reply_text, model = await llm_service.chat(messages)
        result = self._finish(db, conversation, reply_text, lang, model, user_text)
        result["kb_used"] = True  # retrieval attempted; see retrieve() for hits
        return result

    async def reply_stream(
        self, db: Session, conversation: Conversation,
        user_text: str, language_preference: str = "AUTO"
    ) -> AsyncIterator[tuple[str, object]]:
        """Yield ('token', str) deltas, then ('done', result_dict).

        The first sentence is validated for language/script BEFORE anything is
        emitted — a wrong-language start restarts the stream with a correction,
        so the client never sees or speaks the bad text."""
        lang, messages = self._context(db, conversation, user_text, language_preference)
        parts: list[str] = []
        model = ""
        validated = False
        corrected = False
        held: list[str] = []
        stream = llm_service.chat_stream(messages)

        async def refill(new_messages: list[dict]) -> None:
            nonlocal stream, held, validated
            held = []
            stream = llm_service.chat_stream(new_messages)

        while True:
            try:
                delta, m = await stream.__anext__()
            except StopAsyncIteration:
                break
            model = m
            if validated:
                parts.append(delta)
                yield "token", delta
                continue
            held.append(delta)
            joined = "".join(held)
            sents, _ = split_sentences(joined)
            probe = sents[0] if sents else (joined if len(joined) > 200 else "")
            if not probe:
                continue
            if reply_script_ok(probe, user_text, lang) or corrected:
                validated = True
                parts.extend(held)
                for d in held:
                    yield "token", d
                held = []
                continue
            log.warning("reply wrong script, restarting stream with correction")
            corrected = True
            await refill([*messages, {"role": "user",
                                      "content": _CORRECTION.format(label=lang)}])

        if not validated and held:
            # Very short reply — stream ended mid-validation.
            if reply_script_ok("".join(held), user_text, lang) or corrected:
                parts.extend(held)
                for d in held:
                    yield "token", d
            elif not corrected:
                log.warning("short reply wrong script, one correction pass")
                reply_text, model = await llm_service.chat(
                    [*messages, {"role": "user",
                                 "content": _CORRECTION.format(label=lang)}])
                parts.append(reply_text)
                yield "token", reply_text

        if not "".join(parts).strip():
            # One automatic retry on free-tier empty replies.
            log.warning("empty LLM reply, retrying once")
            async for delta, m in llm_service.chat_stream(messages):
                parts.append(delta)
                model = m
                yield "token", delta

        reply_text = "".join(parts).strip()
        if not reply_text:
            raise RuntimeError("Empty reply from model — free-tier hiccup, try again")
        yield "done", self._finish(db, conversation, reply_text, lang, model, user_text)


manager = ConversationManager()
