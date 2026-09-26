-- Every block request, keyed by the caller's idempotency key. A retry with the same key
-- returns the original result instead of acting twice (ADR-0006).
CREATE TABLE card_blocks (
    idempotency_key text PRIMARY KEY,
    card_id         text NOT NULL REFERENCES cards(id),
    customer_id     text NOT NULL REFERENCES customers(id),
    reason          text NOT NULL,
    requested_at    timestamptz NOT NULL DEFAULT now()
);
