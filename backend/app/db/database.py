"""SQLite (local dev) / PostgreSQL (prod) via SQLAlchemy. Same models for both."""
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _resolve_db_url(url: str) -> str:
    # Make relative sqlite paths anchor at the astra/ root so cwd doesn't matter.
    if url.startswith("sqlite:///./"):
        root = Path(__file__).resolve().parents[3]
        return f"sqlite:///{root / url[len('sqlite:///./'):]}"
    return url


DATABASE_URL = _resolve_db_url(settings.DATABASE_URL)
if DATABASE_URL.startswith("sqlite:///"):
    Path(DATABASE_URL[len("sqlite:///"):]).parent.mkdir(parents=True, exist_ok=True)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    from app.models import db_models  # noqa: F401  (register tables)
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
