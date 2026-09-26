"""Bank API tests against a real Postgres (the bank's behaviour *is* its SQL).

Needs TEST_BANK_DATABASE_URL pointing at a migrated database, e.g.
    postgresql://bank_api:bank@localhost:5432/voiceref
The seed is re-applied before each test, so tests are independent.
"""

import os
from collections.abc import Iterator
from importlib.resources import files

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from banking_api import Settings, create_router

URL = os.environ.get("TEST_BANK_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_BANK_DATABASE_URL not set")


@pytest.fixture
def client() -> Iterator[TestClient]:
    assert URL
    with psycopg.connect(URL) as conn:
        conn.execute((files("banking_api") / "seed.sql").read_text().encode())
    app = FastAPI()
    app.include_router(create_router(Settings(database_url=URL)), prefix="/bank")
    with TestClient(app) as c:
        yield c


def test_customer_by_phone(client: TestClient) -> None:
    body = client.get("/bank/customers/by-phone/+919800000001").json()
    assert body["id"] == "CUST-1001"
    assert client.get("/bank/customers/by-phone/+910000000000").status_code == 404


def test_balance_is_integer_paise(client: TestClient) -> None:
    (account,) = client.get("/bank/customers/CUST-1001/accounts").json()
    assert account["balance_paise"] == 8245000
    assert account["currency"] == "INR"


def test_recent_transactions_newest_first(client: TestClient) -> None:
    txns = client.get("/bank/customers/CUST-1001/transactions?limit=3").json()
    assert [t["id"] for t in txns] == ["TXN-5001", "TXN-5002", "TXN-5003"]
    assert txns[0]["amount_paise"] == -199900


def test_cannot_read_another_customers_transaction(client: TestClient) -> None:
    assert client.get("/bank/customers/CUST-1001/transactions/TXN-5001").status_code == 200
    assert client.get("/bank/customers/CUST-1002/transactions/TXN-5001").status_code == 404


def test_block_card_is_idempotent(client: TestClient) -> None:
    req = {"customer_id": "CUST-1001", "reason": "lost", "idempotency_key": "key-00000001"}
    first = client.post("/bank/cards/CARD-3001/block", json=req).json()
    assert first["card"]["status"] == "blocked"
    assert first == {**first, "already_blocked": False, "replayed": False}

    again = client.post("/bank/cards/CARD-3001/block", json=req).json()
    assert again["replayed"] is True
    assert again["card"]["blocked_at"] == first["card"]["blocked_at"]


def test_block_card_rejects_other_customers_card(client: TestClient) -> None:
    req = {"customer_id": "CUST-1002", "reason": "lost", "idempotency_key": "key-00000002"}
    assert client.post("/bank/cards/CARD-3001/block", json=req).status_code == 404


def test_idempotency_key_cannot_be_reused_for_another_card(client: TestClient) -> None:
    req = {"customer_id": "CUST-1001", "reason": "lost", "idempotency_key": "key-00000003"}
    assert client.post("/bank/cards/CARD-3001/block", json=req).status_code == 200
    assert client.post("/bank/cards/CARD-3002/block", json=req).status_code == 409
