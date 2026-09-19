"""Long-term memory: only stores useful facts (policy-gated), keyword retrieval.
Vector embeddings (pgvector) can replace `search` later behind the same API."""
import re
from sqlalchemy.orm import Session
from app.models.db_models import Memory

# Only persist sentences that look like durable info, not every utterance.
_SAVE_PATTERNS = re.compile(
    r"(remember|prefer|my (name|favorite|favourite|project|language)|i (like|love|work on|am working))",
    re.IGNORECASE,
)


def should_save(text: str) -> bool:
    t = (text or "").strip()
    if not t or t.endswith("?"):
        return False  # questions are retrieval, not memories
    if re.match(r"(?i)^(what|which|who|whom|whose|when|where|why|how|is|are|do|does|did|can|could|will|would|tell me|explain)\b", t):
        return False
    return bool(_SAVE_PATTERNS.search(t))


def save_if_useful(db: Session, user_id: str, text: str,
                   memory_type: str = "note", importance: float = 0.6) -> Memory | None:
    if not should_save(text):
        return None
    m = Memory(user_id=user_id, memory_type=memory_type, content=text.strip()[:2000],
               importance=importance)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def search(db: Session, user_id: str, query: str, limit: int = 5) -> list[Memory]:
    """Simple relevance: word overlap. Swap for vector search later."""
    mems = db.query(Memory).filter(Memory.user_id == user_id).all()
    qwords = set(re.findall(r"\w+", (query or "").lower()))
    scored = []
    for m in mems:
        mwords = set(re.findall(r"\w+", m.content.lower()))
        overlap = len(qwords & mwords)
        if overlap:
            scored.append((overlap + m.importance, m))
    scored.sort(key=lambda x: -x[0])
    return [m for _, m in scored[:limit]]
