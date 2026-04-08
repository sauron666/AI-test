"""Centralised settings — loaded from env + YAML."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT_DIR / "config"


class Settings(BaseSettings):
    """Environment-backed runtime settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Core ─────────────────────────────────────────
    sauron_env: str = Field("development", alias="SAURON_ENV")
    sauron_secret_key: str = Field("change-me", alias="SAURON_SECRET_KEY")
    sauron_host: str = Field("0.0.0.0", alias="SAURON_HOST")
    sauron_port: int = Field(8000, alias="SAURON_PORT")
    sauron_web_port: int = Field(8080, alias="SAURON_WEB_PORT")
    sauron_mcp_port: int = Field(8765, alias="SAURON_MCP_PORT")
    sauron_log_level: str = Field("INFO", alias="SAURON_LOG_LEVEL")

    # ── Database ─────────────────────────────────────
    database_url: str = Field("sqlite:///./data/sauron.db", alias="DATABASE_URL")

    # ── LLM providers ────────────────────────────────
    anthropic_api_key: str | None = Field(None, alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field("claude-opus-4-6", alias="ANTHROPIC_MODEL")

    openai_api_key: str | None = Field(None, alias="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4o", alias="OPENAI_MODEL")

    google_api_key: str | None = Field(None, alias="GOOGLE_API_KEY")
    google_model: str = Field("gemini-2.0-pro", alias="GOOGLE_MODEL")

    ollama_host: str = Field("http://localhost:11434", alias="OLLAMA_HOST")
    ollama_model: str = Field("whiterabbitneo:13b", alias="OLLAMA_MODEL")

    default_llm_provider: str = Field("claude", alias="DEFAULT_LLM_PROVIDER")

    # ── Agent ────────────────────────────────────────
    agent_max_iterations: int = Field(50, alias="AGENT_MAX_ITERATIONS")
    agent_planning_model: str = Field("claude", alias="AGENT_PLANNING_MODEL")
    agent_execution_model: str = Field("ollama", alias="AGENT_EXECUTION_MODEL")
    agent_reflection_enabled: bool = Field(True, alias="AGENT_REFLECTION_ENABLED")
    agent_auto_approve_commands: bool = Field(False, alias="AGENT_AUTO_APPROVE_COMMANDS")

    # ── Executor ─────────────────────────────────────
    executor_timeout_seconds: int = Field(900, alias="EXECUTOR_TIMEOUT_SECONDS")
    executor_workdir: str = Field("/tmp/sauron-work", alias="EXECUTOR_WORKDIR")
    executor_screenshots: bool = Field(True, alias="EXECUTOR_SCREENSHOTS")
    executor_record_pty: bool = Field(True, alias="EXECUTOR_RECORD_PTY")

    # ── Stealth ──────────────────────────────────────
    stealth_default_profile: str = Field("normal", alias="STEALTH_DEFAULT_PROFILE")
    stealth_jitter_min_ms: int = Field(200, alias="STEALTH_JITTER_MIN_MS")
    stealth_jitter_max_ms: int = Field(1500, alias="STEALTH_JITTER_MAX_MS")

    # ── Reporting ────────────────────────────────────
    report_company_name: str = Field("Your Security Team", alias="REPORT_COMPANY_NAME")
    report_logo_path: str = Field("frontend/assets/logo.svg", alias="REPORT_LOGO_PATH")
    report_output_dir: str = Field("./reports/output", alias="REPORT_OUTPUT_DIR")

    # ── Auth ─────────────────────────────────────────
    auth_enabled: bool = Field(True, alias="AUTH_ENABLED")
    auth_default_user: str = Field("operator", alias="AUTH_DEFAULT_USER")
    auth_default_password: str = Field("change-me", alias="AUTH_DEFAULT_PASSWORD")

    # ── Helpers ──────────────────────────────────────
    @property
    def root_dir(self) -> Path:
        return ROOT_DIR

    @property
    def config_dir(self) -> Path:
        return CONFIG_DIR

    def load_yaml(self, name: str) -> dict[str, Any]:
        """Load a YAML file from the config directory."""
        path = CONFIG_DIR / name
        if not path.exists():
            return {}
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}


@lru_cache
def get_settings() -> Settings:
    return Settings()


def ensure_runtime_dirs(settings: Settings | None = None) -> None:
    """Create runtime directories if missing."""
    s = settings or get_settings()
    for path in [
        s.root_dir / "data",
        s.root_dir / "logs",
        s.root_dir / "reports" / "output",
        s.root_dir / "screenshots",
        s.root_dir / "artifacts",
        s.root_dir / "sessions",
        Path(s.executor_workdir),
    ]:
        path.mkdir(parents=True, exist_ok=True)
