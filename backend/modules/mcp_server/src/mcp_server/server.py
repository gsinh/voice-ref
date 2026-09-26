"""The banking MCP server: the only way an LLM reaches bank data (ADR-0006).

Security model:
- **Who** the customer is never comes from the model. Every call carries a session
  token (`Authorization: Bearer <jwt>`) issued by the orchestrator after OTP; tools
  read the customer from it, so no tool takes a customer id argument.
- **block_card** additionally needs a confirmation token bound to this customer, this
  action and this card. Its unique id is the bank's idempotency key, so replaying a
  token can never block twice.
"""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from starlette.types import ASGIApp

from mcp_server.formatting import format_inr, format_when
from mcp_server.settings import Settings
from signed_tokens import TokenError, verify_confirmation, verify_session

BLOCK_CARD = "block_card"


@dataclass(frozen=True)
class McpComponent:
    """What the gateway needs to host this module: an ASGI app and its lifespan."""

    app: ASGIApp
    lifespan: Callable[[], AbstractAsyncContextManager[None]]


def create_mcp(settings: Settings) -> McpComponent:
    key = settings.token_signing_key.get_secret_value()
    http = httpx.AsyncClient(base_url=settings.banking_api_url, timeout=settings.bank_timeout_s)

    mcp = FastMCP(
        name="voice-ref-banking",
        instructions="Read-only banking lookups for the authenticated customer, plus block_card.",
        streamable_http_path="/",
        stateless_http=True,  # no MCP session state: any request can go to any process
        json_response=True,
    )

    def customer_id(ctx: Context) -> str:  # type: ignore[type-arg]
        request = ctx.request_context.request
        auth = request.headers.get("authorization", "") if request is not None else ""
        scheme, _, token = auth.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise ToolError("not authenticated")
        try:
            return verify_session(key, token).customer_id
        except TokenError as exc:
            raise ToolError("not authenticated") from exc

    async def bank_get(path: str, **params: Any) -> Any:
        resp = await http.get(path, params=params or None)
        if resp.status_code == 404:
            raise ToolError("not found")
        resp.raise_for_status()
        return resp.json()

    @mcp.tool()
    async def get_customer(ctx: Context) -> dict[str, str]:  # type: ignore[type-arg]
        """The authenticated customer's name and preferred language."""
        c = await bank_get(f"/customers/{customer_id(ctx)}")
        return {"name": c["full_name"], "preferred_language": c["preferred_language"]}

    @mcp.tool()
    async def get_account_balance(ctx: Context) -> list[dict[str, str]]:  # type: ignore[type-arg]
        """Current balance of each of the customer's accounts."""
        accounts = await bank_get(f"/customers/{customer_id(ctx)}/accounts")
        return [
            {
                "account": f"{a['account_type'].title()} account {a['masked_number']}",
                "balance": format_inr(a["balance_paise"]),
            }
            for a in accounts
        ]

    @mcp.tool()
    async def get_recent_transactions(ctx: Context, limit: int = 5) -> list[dict[str, str]]:  # type: ignore[type-arg]
        """The customer's most recent transactions, newest first (max 20)."""
        limit = max(1, min(limit, 20))
        txns = await bank_get(f"/customers/{customer_id(ctx)}/transactions", limit=limit)
        return [_transaction(t) for t in txns]

    @mcp.tool()
    async def get_transaction_details(ctx: Context, transaction_id: str) -> dict[str, str]:  # type: ignore[type-arg]
        """Full details of one of the customer's transactions, by its id (e.g. TXN-5001)."""
        t = await bank_get(f"/customers/{customer_id(ctx)}/transactions/{transaction_id}")
        return {**_transaction(t), "category": t["category"], "card_id": t["card_id"] or "none"}

    @mcp.tool()
    async def get_card_status(ctx: Context) -> list[dict[str, str]]:  # type: ignore[type-arg]
        """The customer's cards and whether each is active or blocked."""
        cards = await bank_get(f"/customers/{customer_id(ctx)}/cards")
        return [
            {
                "card_id": c["id"],
                "card": f"{c['network']} {c['card_type']} card ending {c['last4']}",
                "status": c["status"],
            }
            for c in cards
        ]

    @mcp.tool()
    async def block_card(
        ctx: Context,  # type: ignore[type-arg]
        card_id: str,
        reason: str,
        confirmation_token: str,
    ) -> dict[str, str]:
        """Permanently block a card. Requires a confirmation token proving the customer
        explicitly confirmed blocking this exact card. Safe to retry with the same token."""
        cid = customer_id(ctx)
        try:
            confirmation = verify_confirmation(
                key, confirmation_token, customer_id=cid, action=BLOCK_CARD, target=card_id
            )
        except TokenError as exc:
            raise ToolError("a valid confirmation from the customer is required") from exc
        resp = await http.post(
            f"/cards/{card_id}/block",
            json={
                "customer_id": cid,
                "reason": reason[:200],
                "idempotency_key": confirmation.token_id,
            },
        )
        if resp.status_code in (404, 409):
            raise ToolError("card could not be blocked")
        resp.raise_for_status()
        result = resp.json()
        card = result["card"]
        return {
            "card": f"{card['network']} {card['card_type']} card ending {card['last4']}",
            "status": card["status"],
            "outcome": "already blocked" if result["already_blocked"] else "blocked now",
        }

    app = mcp.streamable_http_app()

    @asynccontextmanager
    async def lifespan() -> AsyncIterator[None]:
        # A mounted Starlette app's own lifespan doesn't run, so the host runs this.
        async with mcp.session_manager.run():
            try:
                yield
            finally:
                await http.aclose()

    return McpComponent(app=app, lifespan=lifespan)


def _transaction(t: dict[str, Any]) -> dict[str, str]:
    amount = t["amount_paise"]
    return {
        "transaction_id": t["id"],
        "when": format_when(datetime.fromisoformat(t["posted_at"])),
        "description": t["description"],
        "merchant": t["merchant"],
        "amount": format_inr(abs(amount)),
        "direction": "debit" if amount < 0 else "credit",
        "channel": t["channel"],
    }
