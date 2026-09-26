"""API shapes of the mock bank. Money is integer paise plus an ISO currency code."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Customer(BaseModel):
    id: str
    full_name: str
    phone: str
    preferred_language: str


class Account(BaseModel):
    id: str
    account_type: Literal["savings", "current"]
    currency: str
    balance_paise: int
    masked_number: str


class Transaction(BaseModel):
    id: str
    account_id: str
    card_id: str | None
    posted_at: datetime
    amount_paise: int = Field(description="Negative = debit, positive = credit")
    merchant: str
    category: str
    channel: str
    description: str


class Card(BaseModel):
    id: str
    account_id: str | None
    card_type: Literal["debit", "credit"]
    network: str
    last4: str
    status: Literal["active", "blocked"]
    blocked_at: datetime | None


class BlockCardRequest(BaseModel):
    customer_id: str
    reason: str = Field(min_length=1, max_length=200)
    idempotency_key: str = Field(min_length=8, max_length=200)


class BlockCardResult(BaseModel):
    card: Card
    already_blocked: bool = Field(description="True if the card was blocked before this request")
    replayed: bool = Field(description="True if this idempotency key was seen before")
