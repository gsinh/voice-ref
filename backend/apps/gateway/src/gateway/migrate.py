"""A deliberately small migration runner.

Each module ships ordered `NNNN_name.sql` files and owns one schema. The runner logs in
as the module's own role, records applied versions in `<schema>.schema_migrations`, and
applies each pending file in its own transaction. An advisory lock makes concurrent
runs (e.g. two deploys) safe. Forward-only: to undo, write a new migration.
"""

import logging
from dataclasses import dataclass
from importlib.resources.abc import Traversable

import psycopg
from psycopg import sql

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class MigrationSet:
    module: str
    database_url: str
    schema: str
    directory: Traversable


def pending(ms: MigrationSet, applied: set[str]) -> list[Traversable]:
    files = sorted(
        (f for f in ms.directory.iterdir() if f.name.endswith(".sql")), key=lambda f: f.name
    )
    return [f for f in files if f.name.removesuffix(".sql") not in applied]


def apply(ms: MigrationSet) -> list[str]:
    """Apply pending migrations for one module. Returns the versions applied."""
    with psycopg.connect(ms.database_url, autocommit=True) as conn:
        conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(ms.schema)))
        conn.execute("SELECT pg_advisory_lock(hashtext(%s))", (ms.module,))
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                " version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
            )
            applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
            done: list[str] = []
            for file in pending(ms, applied):
                version = file.name.removesuffix(".sql")
                with conn.transaction():
                    conn.execute(file.read_text().encode())
                    conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
                log.info("migration applied", extra={"component": ms.module, "version": version})
                done.append(version)
            return done
        finally:
            conn.execute("SELECT pg_advisory_unlock(hashtext(%s))", (ms.module,))


def run_script(database_url: str, schema: str, script: Traversable) -> None:
    """Run one SQL script in a transaction (used for seeding demo data)."""
    with psycopg.connect(database_url) as conn:
        conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        conn.execute(script.read_text().encode())
