"""REST API: sessions, conversations, memories, documents, settings, text chat."""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.database import get_db
from app.models.db_models import Conversation, Document, DocumentChunk, Memory, Message, Setting
from app.schemas.api import ChatTextIn, ConversationCreate, DocumentIn, MemoryCreate, SettingUpdate
from app.services.conversation.manager import manager
from app.services.knowledge.store import add_document
from app.services.memory import short_term

router = APIRouter(prefix="/api")


@router.post("/session/start")
def session_start():
    return {"session_id": str(uuid.uuid4()), "greeting_en": settings.ASTRA_GREETING_EN,
            "greeting_te": settings.ASTRA_GREETING_TE}


@router.post("/session/end")
def session_end():
    return {"ok": True}


@router.post("/conversations")
def create_conversation(body: ConversationCreate, db: Session = Depends(get_db)):
    c = Conversation(title=body.title, language=body.language)
    db.add(c)
    db.commit()
    db.refresh(c)
    return {"id": c.id, "title": c.title, "language": c.language}


@router.get("/conversations")
def list_conversations(db: Session = Depends(get_db)):
    return [{"id": c.id, "title": c.title, "language": c.language,
             "updated_at": c.updated_at.isoformat()} for c in
            db.query(Conversation).order_by(Conversation.updated_at.desc()).limit(50)]


@router.get("/conversations/{cid}/messages")
def get_messages(cid: str, db: Session = Depends(get_db)):
    msgs = short_term.recent_messages(db, cid, limit=100)
    return [{"role": m.role, "content": m.content, "language": m.language,
             "created_at": m.created_at.isoformat()} for m in msgs]


@router.post("/chat/text")
async def chat_text(body: ChatTextIn, db: Session = Depends(get_db)):
    """Same pipeline as voice (minus audio) — useful for testing without a mic."""
    conv = None
    if body.conversation_id:
        conv = db.query(Conversation).filter(Conversation.id == body.conversation_id).first()
    if conv is None:
        conv = Conversation(title=(body.text[:40] or "New conversation"))
        db.add(conv)
        db.commit()
        db.refresh(conv)
    try:
        result = await manager.reply(db, conv, body.text, body.language_preference)
    except RuntimeError as e:
        # No-key / provider-down: friendly JSON instead of a crash (spec §25 failure case)
        return {"conversation_id": conv.id, "reply": str(e), "language": "en",
                "model": "none", "memory_saved": False, "kb_used": False, "error": True}
    conv.updated_at = datetime.utcnow()
    db.commit()
    return {"conversation_id": conv.id, **result}


@router.get("/memories")
def list_memories(db: Session = Depends(get_db)):
    return [{"id": m.id, "memory_type": m.memory_type, "content": m.content,
             "importance": m.importance} for m in db.query(Memory).order_by(Memory.created_at.desc()).limit(100)]


@router.post("/memories")
def create_memory(body: MemoryCreate, db: Session = Depends(get_db)):
    m = Memory(memory_type=body.memory_type, content=body.content, importance=body.importance)
    db.add(m)
    db.commit()
    db.refresh(m)
    return {"id": m.id}


@router.delete("/memories/{mid}")
def delete_memory(mid: str, db: Session = Depends(get_db)):
    m = db.query(Memory).filter(Memory.id == mid).first()
    if not m:
        raise HTTPException(404, "memory not found")
    db.delete(m)
    db.commit()
    return {"ok": True}


@router.post("/documents")
def upload_document(body: DocumentIn, db: Session = Depends(get_db)):
    doc = add_document(db, body.filename, body.content, body.content_type)
    return {"id": doc.id, "filename": doc.filename, "status": doc.status}


@router.get("/documents")
def list_documents(db: Session = Depends(get_db)):
    return [{"id": d.id, "filename": d.filename, "status": d.status} for d in db.query(Document).all()]


@router.delete("/documents/{did}")
def delete_document(did: str, db: Session = Depends(get_db)):
    db.query(DocumentChunk).filter(DocumentChunk.document_id == did).delete()
    d = db.query(Document).filter(Document.id == did).first()
    if not d:
        raise HTTPException(404, "document not found")
    db.delete(d)
    db.commit()
    return {"ok": True}


@router.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    rows = db.query(Setting).all()
    out = {r.key: r.value for r in rows}
    out.setdefault("language", settings.DEFAULT_LANGUAGE)
    out.setdefault("llm_model", settings.LLM_MODEL)
    return out


@router.put("/settings/{key}")
def put_setting(key: str, body: SettingUpdate, db: Session = Depends(get_db)):
    r = db.query(Setting).filter(Setting.key == key).first()
    if r is None:
        r = Setting(key=key, value=body.value)
        db.add(r)
    else:
        r.value = body.value
        r.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True}
