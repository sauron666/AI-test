"""FastAPI dependencies — auth, db, etc."""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from ..database.models import User
from ..database.session import db_session
from ..settings import get_settings
from ..utils.security import decode_token


async def current_user(authorization: str | None = Header(default=None)) -> User:
    settings = get_settings()
    if not settings.auth_enabled:
        with db_session() as s:
            u = s.query(User).filter_by(username=settings.auth_default_user).first()
            if not u:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "default user missing")
            return u

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")
    with db_session() as s:
        u = s.query(User).filter_by(username=payload["sub"]).first()
        if not u:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found")
        return u


def require_role(*roles: str):
    def _check(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient role")
        return user
    return _check
