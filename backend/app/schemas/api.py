from pydantic import BaseModel


class ConversationCreate(BaseModel):
    title: str = "New conversation"
    language: str = "AUTO"


class MemoryCreate(BaseModel):
    memory_type: str = "note"
    content: str
    importance: float = 0.5


class SettingUpdate(BaseModel):
    value: str


class ChatTextIn(BaseModel):
    """Text fallback (no mic) — same pipeline as voice, minus STT/TTS audio."""
    conversation_id: str | None = None
    text: str
    language_preference: str = "AUTO"


class DocumentIn(BaseModel):
    filename: str
    content: str
    content_type: str = "text/plain"
