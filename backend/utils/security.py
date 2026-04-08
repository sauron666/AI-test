"""Security utilities — hashing, JWT, command validation."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from ..settings import get_settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Patterns that must NEVER reach the executor, regardless of who asked.
HARD_BANNED_PATTERNS = [
    r"\brm\s+-rf\s+/(?!\w)",           # rm -rf /
    r":\(\)\s*\{\s*:\|:&\s*\};:",      # fork bomb
    r"\bmkfs\.\w+\b",                   # format fs
    r"\bdd\s+if=/dev/(zero|random)\s+of=/dev/",
    r"\b>\s*/dev/sd[a-z]",              # raw disk writes
    r"\bshutdown\b|\breboot\b|\bhalt\b",
]

_banned_re = re.compile("|".join(HARD_BANNED_PATTERNS), re.IGNORECASE)


def hash_password(raw: str) -> str:
    return _pwd_context.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return _pwd_context.verify(raw, hashed)
    except Exception:
        return False


def create_access_token(subject: str, expires_minutes: int = 480, extra: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    to_encode: dict[str, Any] = {"sub": subject}
    if extra:
        to_encode.update(extra)
    to_encode["exp"] = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    return jwt.encode(to_encode, settings.sauron_secret_key, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any] | None:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.sauron_secret_key, algorithms=["HS256"])
    except JWTError:
        return None


def is_command_banned(command: str) -> bool:
    """Hard block for destructive patterns — executor will refuse."""
    return bool(_banned_re.search(command))
