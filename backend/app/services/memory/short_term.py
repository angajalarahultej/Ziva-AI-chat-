"""Short-term: last N messages of a conversation (bounded context window)."""
from sqlalchemy.orm import Session
from app.models.db_models import Message

WINDOW = 20


def recent_messages(db: Session, conversation_id: str, limit: int = WINDOW) -> list[Message]:
    return (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .all()[::-1]
    )


def save_message(db: Session, conversation_id: str, role: str, content: str, language: str) -> Message:
    m = Message(conversation_id=conversation_id, role=role, content=content, language=language)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m
