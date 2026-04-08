"""SQLAlchemy ORM models for SAURON."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="operator")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Engagement(Base):
    """A whole pentest job."""
    __tablename__ = "engagements"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    profile: Mapped[str] = mapped_column(String(64))       # web, api, ad, ...
    scope: Mapped[dict] = mapped_column(JSON, default=dict)
    rules_of_engagement: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="created")
    stealth_profile: Mapped[str] = mapped_column(String(32), default="normal")
    llm_provider: Mapped[str] = mapped_column(String(32), default="claude")
    llm_model: Mapped[str] = mapped_column(String(128), default="")
    created_by: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    events: Mapped[list["AgentEvent"]] = relationship(back_populates="engagement", cascade="all, delete-orphan")
    findings: Mapped[list["Finding"]] = relationship(back_populates="engagement", cascade="all, delete-orphan")
    commands: Mapped[list["CommandRun"]] = relationship(back_populates="engagement", cascade="all, delete-orphan")


class AgentEvent(Base):
    """Every plan/thought/reflect the AI emits."""
    __tablename__ = "agent_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    engagement_id: Mapped[str] = mapped_column(String, ForeignKey("engagements.id", ondelete="CASCADE"))
    phase: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(32))   # thought | action | observation | reflection | error
    content: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    engagement: Mapped[Engagement] = relationship(back_populates="events")


class CommandRun(Base):
    """Every command the executor ran — with evidence."""
    __tablename__ = "command_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    engagement_id: Mapped[str] = mapped_column(String, ForeignKey("engagements.id", ondelete="CASCADE"))
    tool: Mapped[str] = mapped_column(String(64))
    command: Mapped[str] = mapped_column(Text)
    exit_code: Mapped[int] = mapped_column(Integer, default=0)
    stdout_path: Mapped[str] = mapped_column(String(512), default="")
    stderr_path: Mapped[str] = mapped_column(String(512), default="")
    screenshot_path: Mapped[str] = mapped_column(String(512), default="")
    pty_record_path: Mapped[str] = mapped_column(String(512), default="")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    engagement: Mapped[Engagement] = relationship(back_populates="commands")


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    engagement_id: Mapped[str] = mapped_column(String, ForeignKey("engagements.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255))
    severity: Mapped[str] = mapped_column(String(16))   # info | low | medium | high | critical
    cvss: Mapped[float] = mapped_column(default=0.0)
    cwe: Mapped[str] = mapped_column(String(32), default="")
    mitre_attack: Mapped[str] = mapped_column(String(64), default="")
    owasp: Mapped[str] = mapped_column(String(64), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    impact: Mapped[str] = mapped_column(Text, default="")
    remediation: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    confirmed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    engagement: Mapped[Engagement] = relationship(back_populates="findings")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    engagement_id: Mapped[str] = mapped_column(String, ForeignKey("engagements.id", ondelete="CASCADE"))
    format: Mapped[str] = mapped_column(String(16))   # md | html | pdf | json
    path: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
