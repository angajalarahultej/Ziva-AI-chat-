"""Knowledge store: chunk → keyword retrieval. Vector DB can replace `retrieve` later."""
import re
from sqlalchemy.orm import Session
from app.models.db_models import Document, DocumentChunk

CHUNK_SIZE = 800


def chunk_text(text: str, size: int = CHUNK_SIZE) -> list[str]:
    text = (text or "").strip()
    return [text[i:i + size] for i in range(0, len(text), size)] or [""]


def add_document(db: Session, filename: str, content: str, content_type: str = "text/plain") -> Document:
    doc = Document(filename=filename, content_type=content_type, status="indexed")
    db.add(doc)
    db.commit()
    db.refresh(doc)
    for i, ch in enumerate(chunk_text(content)):
        db.add(DocumentChunk(document_id=doc.id, chunk_index=i, content=ch))
    db.commit()
    return doc


def retrieve(db: Session, query: str, limit: int = 3) -> list[str]:
    chunks = db.query(DocumentChunk).all()
    qwords = set(re.findall(r"\w+", (query or "").lower()))
    scored = []
    for c in chunks:
        cwords = set(re.findall(r"\w+", c.content.lower()))
        overlap = len(qwords & cwords)
        if overlap:
            scored.append((overlap, c.content))
    scored.sort(key=lambda x: -x[0])
    return [c for _, c in scored[:limit]]
