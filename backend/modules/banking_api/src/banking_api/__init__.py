"""Mock bank system of record: customers, accounts, cards, transactions.

Owns the `bank` schema. Phase 0: schema, seed data and an info route.
Phase 1 adds the read APIs and block-card.
"""

from importlib.resources import files

from banking_api.router import create_router
from banking_api.settings import Settings

SCHEMA = "bank"
MIGRATIONS = files(__package__) / "migrations"
SEED = files(__package__) / "seed.sql"

__all__ = ["MIGRATIONS", "SCHEMA", "SEED", "Settings", "create_router"]
