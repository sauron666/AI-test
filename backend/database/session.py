"""Database session & bootstrap."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ..settings import ensure_runtime_dirs, get_settings
from ..utils.security import hash_password
from .models import Base, User

_engine = None
_Session: sessionmaker[Session] | None = None


def init_engine() -> None:
    global _engine, _Session
    if _engine is not None:
        return
    settings = get_settings()
    ensure_runtime_dirs(settings)
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    _engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
    _Session = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(_engine)
    _ensure_default_user()


def _ensure_default_user() -> None:
    assert _Session is not None
    settings = get_settings()
    with _Session() as s:
        if s.query(User).filter_by(username=settings.auth_default_user).first():
            return
        s.add(
            User(
                username=settings.auth_default_user,
                password_hash=hash_password(settings.auth_default_password),
                role="admin",
            )
        )
        s.commit()


@contextmanager
def db_session() -> Iterator[Session]:
    if _Session is None:
        init_engine()
    assert _Session is not None
    s = _Session()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
