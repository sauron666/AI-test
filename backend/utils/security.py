"""Security utilities — password hashing, JWT, command validation.

Password hashing uses `bcrypt` directly. We used to go through
`passlib`, but passlib is unmaintained and breaks on bcrypt>=4
(`module 'bcrypt' has no attribute '__about__'`), so we dropped it.
Truncation to 72 bytes is explicit to match bcrypt's hard limit.

JWT backend prefers `pyjwt` (actively maintained) and falls back to
`python-jose` for environments that still ship it. Public API
(`hash_password`, `verify_password`, `create_access_token`,
`decode_token`, `is_command_banned`) is stable.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt

try:
    import jwt as _pyjwt  # type: ignore

    _JWT_BACKEND = "pyjwt"

    def _jwt_encode(payload: dict[str, Any], secret: str, algorithm: str) -> str:
        token = _pyjwt.encode(payload, secret, algorithm=algorithm)
        # pyjwt<2 returned bytes; pyjwt>=2 returns str — normalise.
        return token.decode("utf-8") if isinstance(token, bytes) else token

    def _jwt_decode(token: str, secret: str, algorithms: list[str]) -> dict[str, Any]:
        return _pyjwt.decode(token, secret, algorithms=algorithms)

    class JWTError(Exception):  # type: ignore
        pass

    _JWT_EXC: tuple[type[BaseException], ...] = (
        getattr(_pyjwt, "PyJWTError", Exception),
    )
except ImportError:  # pragma: no cover
    from jose import JWTError as _JoseError, jwt as _jose  # type: ignore

    _JWT_BACKEND = "jose"
    JWTError = _JoseError  # type: ignore

    def _jwt_encode(payload: dict[str, Any], secret: str, algorithm: str) -> str:
        return _jose.encode(payload, secret, algorithm=algorithm)

    def _jwt_decode(token: str, secret: str, algorithms: list[str]) -> dict[str, Any]:
        return _jose.decode(token, secret, algorithms=algorithms)

    _JWT_EXC = (_JoseError,)

from ..settings import get_settings

# ── password hashing ────────────────────────────────
# bcrypt's hard limit is 72 bytes. Anything longer is silently
# truncated by the library on some versions and raises ValueError
# on others — we normalise by pre-truncating in one place.
_BCRYPT_MAX = 72


def _to_bytes(secret: str | bytes) -> bytes:
    if isinstance(secret, bytes):
        raw = secret
    else:
        raw = secret.encode("utf-8")
    if len(raw) > _BCRYPT_MAX:
        raw = raw[:_BCRYPT_MAX]
    return raw


def hash_password(raw: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(_to_bytes(raw), salt).decode("utf-8")


def verify_password(raw: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(_to_bytes(raw), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ── JWT ─────────────────────────────────────────────
def create_access_token(subject: str, expires_minutes: int = 480, extra: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    to_encode: dict[str, Any] = {"sub": subject}
    if extra:
        to_encode.update(extra)
    to_encode["exp"] = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    return _jwt_encode(to_encode, settings.sauron_secret_key, "HS256")


def decode_token(token: str) -> dict[str, Any] | None:
    settings = get_settings()
    try:
        return _jwt_decode(token, settings.sauron_secret_key, ["HS256"])
    except _JWT_EXC:
        return None


# ── command validation ─────────────────────────────
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


def is_command_banned(command: str) -> bool:
    """Hard block for destructive patterns — executor will refuse."""
    return bool(_banned_re.search(command))
