"""MCP server exposing banking tools: the only way the LLM reaches bank data (ADR-0006).

Phase 0: health endpoints only. Phase 1 mounts the FastMCP tools at /mcp.
"""

from mcp_server.settings import get_settings
from voiceref_common import create_app

app = create_app(get_settings())
