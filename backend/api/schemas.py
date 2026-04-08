"""Pydantic request/response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class EngagementCreate(BaseModel):
    name: str
    profile: str
    scope: dict[str, Any] = Field(default_factory=dict)
    rules_of_engagement: str = ""
    stealth_profile: str = "normal"
    llm_provider: str | None = None
    llm_model: str | None = None


class EngagementOut(BaseModel):
    id: str
    name: str
    profile: str
    scope: dict[str, Any]
    rules_of_engagement: str
    status: str
    stealth_profile: str
    llm_provider: str
    llm_model: str
    created_at: datetime

    class Config:
        from_attributes = True


class FindingOut(BaseModel):
    id: str
    title: str
    severity: str
    cvss: float
    cwe: str
    owasp: str
    mitre_attack: str
    summary: str
    description: str
    impact: str
    remediation: str
    evidence: dict[str, Any]
    confirmed: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CommandOut(BaseModel):
    id: str
    tool: str
    command: str
    exit_code: int
    duration_ms: int
    stdout_path: str
    stderr_path: str
    screenshot_path: str
    started_at: datetime

    class Config:
        from_attributes = True
