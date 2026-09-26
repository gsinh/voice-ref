"""MCP server: the only way the LLM reaches bank data (ADR-0006).

Phase 1 mounts the FastMCP tools.
"""

from mcp_server.router import create_router
from mcp_server.settings import Settings

__all__ = ["Settings", "create_router"]
