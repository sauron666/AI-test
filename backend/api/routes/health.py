"""Health / version endpoints."""
from fastapi import APIRouter

from ... import __version__

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": __version__, "service": "sauron"}


@router.get("/version")
async def version() -> dict:
    return {"version": __version__}
