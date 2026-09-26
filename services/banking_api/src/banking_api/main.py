"""Mock bank system of record: customers, accounts, cards, transactions.

Phase 0: health endpoints only; schema and seed data live in infra/postgres.
Phase 1 adds the read APIs and block-card.
"""

from banking_api.settings import get_settings
from voiceref_common import create_app, postgres_check

settings = get_settings()
app = create_app(settings, {"postgres": postgres_check(settings.database_url)})
