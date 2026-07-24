from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings


def _engine_options(database_url: str) -> dict:
    url = make_url(database_url)
    if url.drivername.startswith("sqlite"):
        if url.database and url.database != ":memory:":
            Path(url.database).parent.mkdir(parents=True, exist_ok=True)

        options: dict = {"connect_args": {"check_same_thread": False}}
        if url.database == ":memory:":
            options["poolclass"] = StaticPool
        return options

    return {}


def build_engine(database_url: str | None = None) -> Engine:
    resolved_url = database_url or get_settings().database_url
    return create_engine(resolved_url, future=True, **_engine_options(resolved_url))


engine = build_engine()
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True,
)


def configure_database(database_url: str) -> None:
    global engine, SessionLocal
    engine.dispose()
    engine = build_engine(database_url)
    SessionLocal.configure(bind=engine)


def get_db():
    db: Session = SessionLocal()

    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
