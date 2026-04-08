"""Tool catalog + direct run endpoint (operator-driven, not agent-driven)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ...database.models import User
from ...tools import get_catalog, get_executor
from ..deps import current_user

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("")
async def list_tools(_: User = Depends(current_user)) -> list[dict[str, Any]]:
    return [t.to_dict() for t in get_catalog().all()]


@router.post("/run")
async def run_tool(payload: dict[str, Any], _: User = Depends(current_user)) -> dict[str, Any]:
    tool_name = payload.get("tool", "")
    args = payload.get("args", "")
    target = payload.get("target", "")
    engagement_id = payload.get("engagement_id", "adhoc")
    spec = get_catalog().get(tool_name)
    if not spec:
        return {"error": f"unknown tool: {tool_name}"}
    command = f"{spec.cmd} {args} {target}".strip()
    result = await get_executor().run(command, tool=tool_name, engagement_id=engagement_id)
    return result.to_dict()
