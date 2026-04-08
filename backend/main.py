"""SAURON entry-point.

Boots the FastAPI backend, static web dashboard, MCP server, and
background workers in a single process (sufficient for solo operators
and hackathon demos; docker-compose splits them for team deployments).
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api.routes import auth as auth_routes
from .api.routes import engagements as engagement_routes
from .api.routes import health as health_routes
from .api.routes import llm as llm_routes
from .api.routes import tools as tool_routes
from .api.websocket import router as ws_router
from .database.session import init_engine
from .mcp.server import SauronMCPServer
from .settings import ensure_runtime_dirs, get_settings
from .utils.logger import configure_logging, get_logger

log = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    ensure_runtime_dirs()
    init_engine()
    log.info("SAURON boot — the Eye is opening…")

    mcp = SauronMCPServer()
    await mcp.start()
    app.state.mcp = mcp

    try:
        yield
    finally:
        log.info("SAURON shutdown — the Eye closes.")
        await mcp.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="SAURON",
        description="The All-Seeing AI for Autonomous Penetration Testing",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # REST routes (always registered FIRST so API paths take priority)
    app.include_router(health_routes.router)
    app.include_router(auth_routes.router)
    app.include_router(engagement_routes.router)
    app.include_router(tool_routes.router)
    app.include_router(llm_routes.router)

    # WebSocket
    app.include_router(ws_router)

    # Static frontend (served on the same port for single-process mode).
    # We mount at "/" so the browser can resolve relative asset paths
    # (css/style.css, js/app.js, assets/favicon.svg) without needing a
    # /ui prefix. FastAPI resolves registered routes BEFORE falling
    # through to the static mount, so /api/* and /ws keep working.
    frontend_dir = Path(settings.root_dir) / "frontend"
    if frontend_dir.exists():
        app.mount(
            "/",
            StaticFiles(directory=str(frontend_dir), html=True),
            name="frontend",
        )

    return app


app = create_app()


def cli() -> None:
    settings = get_settings()
    uvicorn.run(
        "backend.main:app",
        host=settings.sauron_host,
        port=settings.sauron_port,
        reload=False,
        log_level=settings.sauron_log_level.lower(),
    )


if __name__ == "__main__":
    cli()
