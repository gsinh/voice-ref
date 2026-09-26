"""Real adapters for the orchestrator's ports: HTTP to the bank, MCP for tools."""

from typing import Any
from urllib.parse import quote

import httpx
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from orchestrator.ports import Customer, ToolCallError
from signed_tokens import issue_session


class HttpCustomerDirectory:
    def __init__(self, bank_api_url: str, timeout_s: float = 5.0) -> None:
        self._http = httpx.AsyncClient(base_url=bank_api_url, timeout=timeout_s)

    async def by_phone(self, phone: str) -> Customer | None:
        resp = await self._http.get(f"/customers/by-phone/{quote(phone)}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        c = resp.json()
        return Customer(id=c["id"], name=c["full_name"], phone=c["phone"])

    async def aclose(self) -> None:
        await self._http.aclose()


class McpToolsProvider:
    """Loads the MCP tools with a short-lived session token for one customer.

    The token is minted per turn and never stored in conversation state, so there are no
    long-lived credentials at rest in the checkpointer.
    """

    def __init__(self, mcp_url: str, signing_key: str, session_ttl_s: int) -> None:
        self._url = mcp_url
        self._key = signing_key
        self._ttl = session_ttl_s

    def _client(self, customer_id: str) -> MultiServerMCPClient:
        token = issue_session(self._key, customer_id, self._ttl)
        return MultiServerMCPClient(
            {
                "bank": {
                    "transport": "streamable_http",
                    "url": self._url,
                    "headers": {"Authorization": f"Bearer {token}"},
                }
            }
        )

    async def for_customer(self, customer_id: str) -> dict[str, BaseTool]:
        tools = await self._client(customer_id).get_tools()
        return {tool.name: tool for tool in tools}

    async def call(self, customer_id: str, name: str, args: dict[str, Any]) -> Any:
        async with self._client(customer_id).session("bank") as session:
            result = await session.call_tool(name, args)
        if result.isError:
            text = " ".join(getattr(block, "text", "") for block in result.content)
            raise ToolCallError(f"{name}: {text or 'failed'}")
        data = result.structuredContent
        if data is None:
            raise ToolCallError(f"{name}: no structured result")
        # FastMCP wraps non-object return values (e.g. lists) as {"result": ...}.
        return data["result"] if set(data) == {"result"} else data
