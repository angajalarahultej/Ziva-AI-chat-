from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os
import threading
from app.api.routes import router as api_router
from app.core.logging import get_logger
from app.db.database import init_db
from app.websocket.voice import router as ws_router

log = get_logger("main")
app = FastAPI(title="Ziva", version="0.1.0")

# Extra origins (your Vercel domain) via FRONTEND_URLS env, comma-separated.
_extra_origins = [o.strip() for o in os.getenv("FRONTEND_URLS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", *_extra_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Path(__file__).resolve().parents[3].joinpath("data", "audio").mkdir(parents=True, exist_ok=True)


@app.on_event("startup")
def _startup():
    init_db()
    log.info("Ziva backend online")


init_db()  # also run at import so TestClient (no lifespan) still has tables


def _warm_stt() -> None:
    """Load Whisper in the background so the FIRST mic use isn't the slow one."""
    try:
        from app.services.stt.service import stt_service
        if stt_service.available:
            stt_service._ensure()._load()
            log.info("STT engine warmed up")
    except Exception as e:
        log.warning(f"STT warmup skipped: {e}")


threading.Thread(target=_warm_stt, daemon=True).start()


@app.get("/health")
def health():
    from app.services.stt.service import stt_service
    from app.services.tts.service import tts_service
    from app.core.config import settings
    return {"status": "ok", "llm_model": settings.LLM_MODEL,
            "stt_available": stt_service.available, "tts_available": tts_service.available}


app.include_router(api_router)
app.include_router(ws_router)
app.mount("/audio", StaticFiles(directory="data/audio"), name="audio")
