"""WebSocket layer — live telemetry from the agent to the dashboard."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..utils.logger import get_logger

log = get_logger("api.ws")

router = APIRouter()

_clients: set[WebSocket] = set()
_lock = asyncio.Lock()


async def broadcast(event: dict[str, Any]) -> None:
    """Fan-out an event to every connected dashboard client."""
    if not _clients:
        return
    payload = json.dumps(event, default=str)
    dead: list[WebSocket] = []
    for ws in list(_clients):
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    if dead:
        async with _lock:
            for ws in dead:
                _clients.discard(ws)


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    async with _lock:
        _clients.add(ws)
    log.info("ws client connected (total=%d)", len(_clients))
    try:
        await ws.send_text(json.dumps({"type": "hello", "message": "SAURON is watching"}))
        while True:
            msg = await ws.receive_text()
            # Echo-type protocol for operator inputs
            try:
                data = json.loads(msg)
            except json.JSONDecodeError:
                data = {"raw": msg}
            await broadcast({"type": "operator.message", "data": data})
    except WebSocketDisconnect:
        pass
    finally:
        async with _lock:
            _clients.discard(ws)
        log.info("ws client disconnected (total=%d)", len(_clients))
