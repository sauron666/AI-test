"""Model Context Protocol server — exposes SAURON capabilities."""
from .server import SauronMCPServer, start_mcp_server

__all__ = ["SauronMCPServer", "start_mcp_server"]
