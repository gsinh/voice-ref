-- Mock bank system of record. Owned by the bank_api role.
-- Money is stored as integer paise (1 INR = 100 paise): never use floats for money.
SET ROLE bank_api;
SET search_path = bank;

CREATE TABLE customers (
    id          text PRIMARY KEY,               -- e.g. 'CUST-1001'
    full_name   text NOT NULL,
    phone       text NOT NULL UNIQUE,           -- E.164; used to identify the caller
    preferred_language text NOT NULL DEFAULT 'en',
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE accounts (
    id              text PRIMARY KEY,           -- e.g. 'ACC-2001'
    customer_id     text NOT NULL REFERENCES customers(id),
    account_type    text NOT NULL CHECK (account_type IN ('savings', 'current')),
    currency        char(3) NOT NULL DEFAULT 'INR',
    balance_paise   bigint NOT NULL,
    masked_number   text NOT NULL               -- e.g. 'XXXX4821'
);
CREATE INDEX ON accounts (customer_id);

CREATE TABLE cards (
    id              text PRIMARY KEY,           -- e.g. 'CARD-3001'
    customer_id     text NOT NULL REFERENCES customers(id),
    account_id      text REFERENCES accounts(id),
    card_type       text NOT NULL CHECK (card_type IN ('debit', 'credit')),
    network         text NOT NULL,              -- 'Visa', 'RuPay', 'Mastercard'
    last4           char(4) NOT NULL,
    status          text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'blocked')),
    blocked_at      timestamptz,
    block_reason    text
);
CREATE INDEX ON cards (customer_id);

CREATE TABLE transactions (
    id              text PRIMARY KEY,           -- e.g. 'TXN-5001'
    account_id      text NOT NULL REFERENCES accounts(id),
    card_id         text REFERENCES cards(id),
    posted_at       timestamptz NOT NULL,
    amount_paise    bigint NOT NULL,            -- negative = debit, positive = credit
    merchant        text NOT NULL,
    category        text NOT NULL,
    channel         text NOT NULL CHECK (channel IN ('card', 'upi', 'netbanking', 'autodebit', 'atm', 'transfer')),
    description     text NOT NULL
);
CREATE INDEX ON transactions (account_id, posted_at DESC);

RESET ROLE;
