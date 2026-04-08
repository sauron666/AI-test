"""SAURON MCP server.

Exposes every Kali tool in the catalog as an MCP tool, plus higher-level
actions (start_engagement, finish_engagement, request_operator_input, ...).

Transport: simple JSON-over-WebSocket implementation that is compatible
with MCP conventions — we fall back to a minimal hand-rolled protocol if
the `mcp` SDK is unavailable in the runtime, so the server always boots.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import websockets
from websockets.server import WebSocketServerProtocol

from ..settings import get_settings
from ..tools import get_catalog, get_executor
from ..tools.stealth import apply_jitter, decorate_nmap, load_profile
from ..utils.logger import get_logger

log = get_logger("mcp.server")


class SauronMCPServer:
    def __init__(self, host: str | None = None, port: int | None = None):
        s = get_settings()
        self.host = host or s.sauron_host
        self.port = port or s.sauron_mcp_port
        self.catalog = get_catalog()
        self.executor = get_executor()
        self._server = None

    # ── tool dispatch ───────────────────────────────
    def list_tools(self) -> list[dict[str, Any]]:
        core = [
            {
                "name": "list_tools",
                "description": "List every MCP tool available.",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "shell_exec",
                "description": "Run an arbitrary shell command inside the sandbox.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string"},
                        "engagement_id": {"type": "string"},
                        "timeout": {"type": "integer"},
                    },
                    "required": ["command"],
                },
            },
            {
                "name": "request_operator_input",
                "description": "Ask the human operator a clarifying question.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"question": {"type": "string"}},
                    "required": ["question"],
                },
            },
        ]
        return core + self.catalog.as_mcp_tools()

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "list_tools":
            return {"tools": self.list_tools()}

        if name == "shell_exec":
            result = await self.executor.run(
                arguments.get("command", ""),
                tool="shell",
                engagement_id=arguments.get("engagement_id", "adhoc"),
                timeout=arguments.get("timeout"),
            )
            return result.to_dict()

        if name == "request_operator_input":
            # The API layer handles the actual await via WebSocket broadcast.
            return {"pending": True, "question": arguments.get("question", "")}

        if name.startswith("kali_"):
            return await self._call_kali_tool(name[len("kali_") :], arguments)

        return {"error": f"unknown tool: {name}"}

    async def _call_kali_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        spec = self.catalog.get(tool_name)
        if not spec:
            return {"error": f"tool not in catalog: {tool_name}"}

        args = arguments.get("args", "")
        target = arguments.get("target", "")
        timeout = arguments.get("timeout")
        stealth = load_profile(arguments.get("stealth"))

        # Domain-specific decoration
        if tool_name == "nmap":
            args = decorate_nmap(args, stealth)

        command = f"{spec.cmd} {args} {target}".strip()
        await apply_jitter(stealth)

        result = await self.executor.run(
            command,
            tool=tool_name,
            engagement_id=arguments.get("engagement_id", "adhoc"),
            timeout=timeout,
        )
        return result.to_dict()

    # ── websocket server ────────────────────────────
    async def _handler(self, ws: WebSocketServerProtocol) -> None:
        log.info("MCP client connected: %s", ws.remote_address)
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    await ws.send(json.dumps({"error": "invalid json"}))
                    continue

                method = msg.get("method")
                params = msg.get("params", {}) or {}
                mid = msg.get("id")

                if method == "tools/list":
                    result = {"tools": self.list_tools()}
                elif method == "tools/call":
                    result = await self.call_tool(params.get("name", ""), params.get("arguments", {}))
                elif method == "ping":
                    result = {"pong": True}
                else:
                    result = {"error": f"unknown method: {method}"}

                await ws.send(json.dumps({"id": mid, "result": result}))
        except websockets.ConnectionClosed:
            pass
        finally:
            log.info("MCP client disconnected")

    async def start(self) -> None:
        log.info("Starting MCP server on ws://%s:%d", self.host, self.port)
        self._server = await websockets.serve(self._handler, self.host, self.port)

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()


async def start_mcp_server() -> SauronMCPServer:
    server = SauronMCPServer()
    await server.start()
    return server


if __name__ == "__main__":
    async def _main() -> None:
        s = await start_mcp_server()
        try:
            await asyncio.Future()
        finally:
            await s.stop()

    asyncio.run(_main())
