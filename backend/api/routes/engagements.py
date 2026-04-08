"""Engagement CRUD + run control."""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from ...agents.base import AgentContext
from ...agents.orchestrator import Orchestrator
from ...database.models import Engagement, Finding, User
from ...database.session import db_session
from ...mcp.server import SauronMCPServer
from ...pentest.registry import get_playbook, list_playbooks
from ...reporting.generator import ReportGenerator
from ..deps import current_user
from ..schemas import EngagementCreate, EngagementOut, FindingOut
from ..websocket import broadcast

router = APIRouter(prefix="/api/engagements", tags=["engagements"])

_mcp_singleton = SauronMCPServer()
_orchestrator = Orchestrator(mcp=_mcp_singleton)


@router.get("/profiles")
async def profiles(_: User = Depends(current_user)) -> list[dict[str, Any]]:
    return [p.to_dict() for p in list_playbooks()]


@router.get("", response_model=list[EngagementOut])
async def list_engagements(user: User = Depends(current_user)) -> list[EngagementOut]:
    with db_session() as s:
        rows = s.query(Engagement).order_by(Engagement.created_at.desc()).all()
        return [EngagementOut.model_validate(r) for r in rows]


@router.post("", response_model=EngagementOut)
async def create_engagement(
    payload: EngagementCreate,
    user: User = Depends(current_user),
) -> EngagementOut:
    pb = get_playbook(payload.profile)
    if not pb:
        raise HTTPException(400, f"unknown profile: {payload.profile}")

    with db_session() as s:
        eng = Engagement(
            name=payload.name,
            profile=payload.profile,
            scope=payload.scope,
            rules_of_engagement=payload.rules_of_engagement,
            stealth_profile=payload.stealth_profile,
            llm_provider=payload.llm_provider or "claude",
            llm_model=payload.llm_model or "",
            created_by=user.id,
            status="created",
        )
        s.add(eng)
        s.flush()
        s.refresh(eng)
        return EngagementOut.model_validate(eng)


@router.get("/{engagement_id}", response_model=EngagementOut)
async def get_engagement(engagement_id: str, _: User = Depends(current_user)) -> EngagementOut:
    with db_session() as s:
        eng = s.query(Engagement).filter_by(id=engagement_id).first()
        if not eng:
            raise HTTPException(404, "not found")
        return EngagementOut.model_validate(eng)


@router.post("/{engagement_id}/start")
async def start_engagement(
    engagement_id: str,
    bg: BackgroundTasks,
    _: User = Depends(current_user),
) -> dict:
    with db_session() as s:
        eng = s.query(Engagement).filter_by(id=engagement_id).first()
        if not eng:
            raise HTTPException(404, "not found")
        eng.status = "running"
        scope = dict(eng.scope)
        profile = eng.profile
        roe = eng.rules_of_engagement
        stealth = eng.stealth_profile

    async def _runner():
        ctx = AgentContext(
            engagement_id=engagement_id,
            profile=profile,
            scope=scope,
            rules_of_engagement=roe,
            stealth_profile=stealth,
            broadcast=broadcast,
        )
        try:
            await _orchestrator.run_engagement(ctx)
            with db_session() as s2:
                e2 = s2.query(Engagement).filter_by(id=engagement_id).first()
                if e2:
                    e2.status = "complete"
        except Exception as e:
            with db_session() as s2:
                e2 = s2.query(Engagement).filter_by(id=engagement_id).first()
                if e2:
                    e2.status = f"error: {str(e)[:200]}"
            await broadcast({"type": "engagement.error", "error": str(e)})

    bg.add_task(lambda: asyncio.create_task(_runner()))
    return {"status": "started", "engagement_id": engagement_id}


@router.get("/{engagement_id}/findings", response_model=list[FindingOut])
async def list_findings(engagement_id: str, _: User = Depends(current_user)) -> list[FindingOut]:
    with db_session() as s:
        rows = s.query(Finding).filter_by(engagement_id=engagement_id).all()
        return [FindingOut.model_validate(r) for r in rows]


@router.post("/{engagement_id}/report")
async def build_report(engagement_id: str, _: User = Depends(current_user)) -> dict:
    gen = ReportGenerator()
    md_path = gen.generate_markdown(engagement_id)
    html_path = gen.generate_html(engagement_id)
    pdf_path = gen.generate_pdf(engagement_id)
    return {
        "markdown": str(md_path),
        "html": str(html_path),
        "pdf": str(pdf_path) if pdf_path else None,
    }
