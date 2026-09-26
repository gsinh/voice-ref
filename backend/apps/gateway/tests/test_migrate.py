"""Migration runner tests. The integration test needs a real Postgres:

TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres uv run pytest
"""

import os
import uuid
from pathlib import Path

import psycopg
import pytest
from psycopg import sql

from gateway.migrate import MigrationSet, apply, pending


def _write(directory: Path, files: dict[str, str]) -> None:
    for name, body in files.items():
        (directory / name).write_text(body)


def test_pending_is_ordered_and_skips_applied(tmp_path: Path) -> None:
    _write(tmp_path, {"0002_b.sql": "", "0001_a.sql": "", "0003_c.sql": "", "notes.txt": ""})
    ms = MigrationSet("m", "postgresql://unused", "s", tmp_path)
    assert [f.name for f in pending(ms, {"0002_b"})] == ["0001_a.sql", "0003_c.sql"]


@pytest.fixture
def schema_url() -> object:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    schema = f"test_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    yield url, schema
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def test_apply_is_idempotent_and_atomic(tmp_path: Path, schema_url: tuple[str, str]) -> None:
    url, schema = schema_url
    _write(tmp_path, {"0001_t.sql": "CREATE TABLE t (id int); INSERT INTO t VALUES (1);"})
    ms = MigrationSet("m", url, schema, tmp_path)

    assert apply(ms) == ["0001_t"]
    assert apply(ms) == []  # second run is a no-op

    # A failing migration rolls back entirely and is not recorded.
    _write(tmp_path, {"0002_bad.sql": "CREATE TABLE u (id int); SELECT 1/0;"})
    with pytest.raises(psycopg.errors.DivisionByZero):
        apply(ms)
    with psycopg.connect(url) as conn:
        conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        versions = [r[0] for r in conn.execute("SELECT version FROM schema_migrations")]
        u_exists = conn.execute("SELECT to_regclass('u')").fetchone()
    assert versions == ["0001_t"]
    assert u_exists == (None,)
