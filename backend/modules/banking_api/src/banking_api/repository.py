"""Data access for the bank schema. SQL lives here and nowhere else."""

from psycopg.rows import class_row
from psycopg_pool import AsyncConnectionPool

from banking_api.models import Account, BlockCardResult, Card, Customer, Transaction


class NotFoundError(Exception):
    pass


class BankRepository:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def customer_by_id(self, customer_id: str) -> Customer:
        return await self._one(
            Customer,
            "SELECT id, full_name, phone, preferred_language FROM customers WHERE id = %s",
            (customer_id,),
        )

    async def customer_by_phone(self, phone: str) -> Customer:
        return await self._one(
            Customer,
            "SELECT id, full_name, phone, preferred_language FROM customers WHERE phone = %s",
            (phone,),
        )

    async def accounts(self, customer_id: str) -> list[Account]:
        return await self._many(
            Account,
            "SELECT id, account_type, currency, balance_paise, masked_number"
            " FROM accounts WHERE customer_id = %s ORDER BY id",
            (customer_id,),
        )

    async def transactions(self, customer_id: str, limit: int) -> list[Transaction]:
        return await self._many(
            Transaction,
            "SELECT t.id, t.account_id, t.card_id, t.posted_at, t.amount_paise, t.merchant,"
            " t.category, t.channel, t.description"
            " FROM transactions t JOIN accounts a ON a.id = t.account_id"
            " WHERE a.customer_id = %s ORDER BY t.posted_at DESC LIMIT %s",
            (customer_id, limit),
        )

    async def transaction(self, customer_id: str, transaction_id: str) -> Transaction:
        # Ownership is part of the lookup: another customer's id is simply "not found".
        return await self._one(
            Transaction,
            "SELECT t.id, t.account_id, t.card_id, t.posted_at, t.amount_paise, t.merchant,"
            " t.category, t.channel, t.description"
            " FROM transactions t JOIN accounts a ON a.id = t.account_id"
            " WHERE a.customer_id = %s AND t.id = %s",
            (customer_id, transaction_id),
        )

    async def cards(self, customer_id: str) -> list[Card]:
        return await self._many(
            Card,
            "SELECT id, account_id, card_type, network, last4, status, blocked_at"
            " FROM cards WHERE customer_id = %s ORDER BY id",
            (customer_id,),
        )

    async def block_card(
        self, customer_id: str, card_id: str, reason: str, idempotency_key: str
    ) -> BlockCardResult:
        """Block a card exactly once per idempotency key, atomically."""
        async with self._pool.connection() as conn, conn.transaction():
            card_cur = conn.cursor(row_factory=class_row(Card))
            # Lock the card row so concurrent requests serialise.
            await card_cur.execute(
                "SELECT id, account_id, card_type, network, last4, status, blocked_at"
                " FROM cards WHERE id = %s AND customer_id = %s FOR UPDATE",
                (card_id, customer_id),
            )
            card = await card_cur.fetchone()
            if card is None:
                raise NotFoundError(card_id)

            seen = await conn.execute(
                "SELECT card_id FROM card_blocks WHERE idempotency_key = %s", (idempotency_key,)
            )
            previous = await seen.fetchone()
            if previous is not None:
                if previous[0] != card_id:
                    raise ValueError("idempotency key was used for a different card")
                return BlockCardResult(card=card, already_blocked=True, replayed=True)

            await conn.execute(
                "INSERT INTO card_blocks (idempotency_key, card_id, customer_id, reason)"
                " VALUES (%s, %s, %s, %s)",
                (idempotency_key, card_id, customer_id, reason),
            )
            if card.status == "blocked":
                return BlockCardResult(card=card, already_blocked=True, replayed=False)

            await card_cur.execute(
                "UPDATE cards SET status = 'blocked', blocked_at = now(), block_reason = %s"
                " WHERE id = %s"
                " RETURNING id, account_id, card_type, network, last4, status, blocked_at",
                (reason, card_id),
            )
            updated = await card_cur.fetchone()
            if updated is None:  # impossible: the row is locked above
                raise NotFoundError(card_id)
            return BlockCardResult(card=updated, already_blocked=False, replayed=False)

    async def _one[T](self, model: type[T], query: str, params: tuple[object, ...]) -> T:
        rows = await self._many(model, query, params)
        if not rows:
            raise NotFoundError(params[-1])
        return rows[0]

    async def _many[T](self, model: type[T], query: str, params: tuple[object, ...]) -> list[T]:
        async with self._pool.connection() as conn:
            cur = conn.cursor(row_factory=class_row(model))
            await cur.execute(query.encode(), params)
            return await cur.fetchall()
