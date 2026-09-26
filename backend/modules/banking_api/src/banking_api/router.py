"""HTTP API of the mock bank. Every read is scoped to a customer: there is no endpoint
that returns another customer's data, whatever the caller asks for."""

from collections.abc import AsyncIterator, Awaitable
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from psycopg_pool import AsyncConnectionPool

from banking_api.models import (
    Account,
    BlockCardRequest,
    BlockCardResult,
    Card,
    Customer,
    Transaction,
)
from banking_api.repository import BankRepository, NotFoundError
from banking_api.settings import Settings


def _repo(request: Request) -> BankRepository:
    repo: BankRepository = request.app.state.bank_repo
    return repo


Repo = Annotated[BankRepository, Depends(_repo)]


def create_router(settings: Settings) -> APIRouter:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # One pool per process; opened lazily so startup doesn't fail if the DB is waking up
        # (Neon scales to zero). Readiness reports the DB state separately.
        pool = AsyncConnectionPool(
            settings.database_url, min_size=0, max_size=settings.pool_max_size, open=False
        )
        await pool.open(wait=False)
        app.state.bank_repo = BankRepository(pool)
        try:
            yield
        finally:
            await pool.close()

    router = APIRouter(tags=["banking_api"], lifespan=lifespan)

    @router.get("/")
    async def info() -> dict[str, str]:
        return {"module": "banking_api", "status": "ok"}

    @router.get("/customers/by-phone/{phone}")
    async def customer_by_phone(phone: str, r: Repo) -> Customer:
        return await _found(r.customer_by_phone(phone))

    @router.get("/customers/{customer_id}")
    async def customer(customer_id: str, r: Repo) -> Customer:
        return await _found(r.customer_by_id(customer_id))

    @router.get("/customers/{customer_id}/accounts")
    async def accounts(customer_id: str, r: Repo) -> list[Account]:
        return await r.accounts(customer_id)

    @router.get("/customers/{customer_id}/transactions")
    async def transactions(
        customer_id: str, r: Repo, limit: Annotated[int, Query(ge=1, le=50)] = 10
    ) -> list[Transaction]:
        return await r.transactions(customer_id, limit)

    @router.get("/customers/{customer_id}/transactions/{transaction_id}")
    async def transaction(customer_id: str, transaction_id: str, r: Repo) -> Transaction:
        return await _found(r.transaction(customer_id, transaction_id))

    @router.get("/customers/{customer_id}/cards")
    async def cards(customer_id: str, r: Repo) -> list[Card]:
        return await r.cards(customer_id)

    @router.post("/cards/{card_id}/block")
    async def block_card(card_id: str, body: BlockCardRequest, r: Repo) -> BlockCardResult:
        try:
            return await r.block_card(body.customer_id, card_id, body.reason, body.idempotency_key)
        except NotFoundError as exc:
            raise HTTPException(404, "card not found") from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    return router


async def _found[T](aw: Awaitable[T]) -> T:
    try:
        return await aw
    except NotFoundError as exc:
        raise HTTPException(404, "not found") from exc
