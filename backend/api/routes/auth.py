"""Authentication routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ...database.models import User
from ...database.session import db_session
from ...utils.security import create_access_token, verify_password
from ..schemas import LoginRequest, LoginResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest) -> LoginResponse:
    with db_session() as s:
        u: User | None = s.query(User).filter_by(username=payload.username).first()
        if not u or not verify_password(payload.password, u.password_hash):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
        token = create_access_token(subject=u.username, extra={"role": u.role})
        return LoginResponse(access_token=token, username=u.username, role=u.role)
