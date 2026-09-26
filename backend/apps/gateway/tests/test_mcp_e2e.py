"""End to end over real HTTP: MCP client -> /mcp -> /bank -> Postgres.

Needs TEST_BANK_DATABASE_URL (a migrated database, bank_api role).
"""

import os
import socket
import threading
import time
from collections.abc import Iterator
from importlib.resources import files
from typing import Any

import psycopg
import pytest
import uvicorn
from langchain_mcp_adapters.client import MultiServerMCPClient

from signed_tokens import issue_confirmation, issue_session

BANK_URL = os.environ.get("TEST_BANK_DATABASE_URL")
pytestmark = pytest.mark.skipif(not BANK_URL, reason="TEST_BANK_DATABASE_URL not set")
KEY = "e2e-signing-key-" + "x" * 32


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]
        return port


@pytest.fixture(scope="module")
def base_url() -> Iterator[str]:
    assert BANK_URL
    port = _free_port()
    mp = pytest.MonkeyPatch()
    mp.setenv("TOKEN_SIGNING_KEY", KEY)
    mp.setenv("BANK_DATABASE_URL", BANK_URL)
    mp.setenv("MCP_BANKING_API_URL", f"http://127.0.0.1:{port}/bank")
    from gateway.app import create_app

    server = uvicorn.Server(uvicorn.Config(create_app(), port=port, log_config=None))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)
    mp.undo()


@pytest.fixture(autouse=True)
def _seed() -> None:
    assert BANK_URL
    with psycopg.connect(BANK_URL) as conn:
        conn.execute((files("banking_api") / "seed.sql").read_text().encode())


async def _call(base_url: str, tool: str, args: dict[str, Any], token: str | None) -> Any:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    client = MultiServerMCPClient(
        {"bank": {"transport": "streamable_http", "url": f"{base_url}/mcp/", "headers": headers}}
    )
    tools = {t.name: t for t in await client.get_tools()}
    return await tools[tool].ainvoke(args)


async def test_lists_all_six_tools(base_url: str) -> None:
    client = MultiServerMCPClient(
        {"bank": {"transport": "streamable_http", "url": f"{base_url}/mcp/"}}
    )
    names = sorted(t.name for t in await client.get_tools())
    assert names == [
        "block_card",
        "get_account_balance",
        "get_card_status",
        "get_customer",
        "get_recent_transactions",
        "get_transaction_details",
    ]


async def test_no_tool_takes_a_customer_id(base_url: str) -> None:
    client = MultiServerMCPClient(
        {"bank": {"transport": "streamable_http", "url": f"{base_url}/mcp/"}}
    )
    for tool in await client.get_tools():
        assert "customer_id" not in tool.args


async def test_requires_a_session(base_url: str) -> None:
    out = await _call(base_url, "get_account_balance", {}, token=None)
    assert "not authenticated" in str(out)


async def test_balance_comes_formatted(base_url: str) -> None:
    out = await _call(base_url, "get_account_balance", {}, issue_session(KEY, "CUST-1001"))
    assert "₹82,450.00" in str(out)


async def test_session_decides_whose_data(base_url: str) -> None:
    out = await _call(base_url, "get_account_balance", {}, issue_session(KEY, "CUST-1002"))
    assert "₹1,56,320.50" in str(out)
    assert "82,450" not in str(out)


async def test_block_card_needs_matching_confirmation(base_url: str) -> None:
    session = issue_session(KEY, "CUST-1001")
    args = {"card_id": "CARD-3001", "reason": "lost"}

    forged = await _call(base_url, "block_card", {**args, "confirmation_token": "x"}, session)
    assert "confirmation" in str(forged)

    other_card = issue_confirmation(KEY, "CUST-1001", "block_card", "CARD-3002")
    wrong = await _call(base_url, "block_card", {**args, "confirmation_token": other_card}, session)
    assert "confirmation" in str(wrong)

    token = issue_confirmation(KEY, "CUST-1001", "block_card", "CARD-3001")
    first = await _call(base_url, "block_card", {**args, "confirmation_token": token}, session)
    assert "blocked now" in str(first)
    replay = await _call(base_url, "block_card", {**args, "confirmation_token": token}, session)
    assert "already blocked" in str(replay)
