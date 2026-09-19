"""LLM context builder — bounded, relevance-gated."""
from app.core.astra_prompt import ASTRA_SYSTEM_PROMPT

VOICE_STYLE = (
    "MOST IMPORTANT RULE: mirror the user's language and script exactly. "
    "English message in → English reply out. Telugu message in → Telugu reply out. "
    "Never switch languages on your own. "
    "VOICE MODE: Your reply will be spoken aloud. Keep it short and speakable: "
    "1-3 sentences unless the user explicitly asks for detail. "
    "Plain text only — no markdown, no bullet lists, no code blocks, no emojis, "
    "no URLs, no romanized words in brackets."
)


def build_messages(user_text: str, lang: str, history, memories, kb_chunks,
                   voice_style: bool = True) -> list[dict]:
    msgs: list[dict] = [{"role": "system", "content": ASTRA_SYSTEM_PROMPT}]
    if voice_style:
        msgs.append({"role": "system", "content": VOICE_STYLE})
    if memories:
        mem_txt = "\n".join(f"- [{m.memory_type}] {m.content}" for m in memories)
        msgs.append({"role": "system",
                     "content": f"Relevant long-term memories (use only if relevant):\n{mem_txt}"})
    if kb_chunks:
        msgs.append({"role": "system",
                     "content": "Relevant knowledge-base context:\n" + "\n---\n".join(kb_chunks)})
    for m in history[-10:]:
        msgs.append({"role": m.role, "content": m.content})
    # history already includes the latest user msg; ensure exactly one trailing user turn
    if not msgs or msgs[-1].get("role") != "user":
        msgs.append({"role": "user", "content": user_text})
    return msgs
