"""LLM provider / model introspection + ad-hoc chat."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ...database.models import User
from ...llm import get_router
from ...llm.base import LLMMessage
from ..deps import current_user

router = APIRouter(prefix="/api/llm", tags=["llm"])


@router.get("/providers")
async def providers(_: User = Depends(current_user)) -> dict[str, Any]:
    r = get_router()
    return {
        "catalog": r.catalog(),
        "available": r.available_providers(),
    }


@router.post("/chat")
async def chat(payload: dict[str, Any], _: User = Depends(current_user)) -> dict[str, Any]:
    r = get_router()
    provider = payload.get("provider") or None
    llm = r.get(provider) if provider else r.for_role("planning")
    messages = [
        LLMMessage(role=m.get("role", "user"), content=m.get("content", ""))
        for m in payload.get("messages", [])
    ]
    resp = await llm.complete(messages, temperature=payload.get("temperature", 0.4))
    return {"content": resp.content, "model": resp.model, "usage": resp.usage}
