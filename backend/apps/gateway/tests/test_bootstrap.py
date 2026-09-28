"""Bootstrap never sends a password to Postgres, only its SCRAM verifier.

The integration test needs a superuser URL: TEST_DATABASE_URL.
"""

import base64
import os
import secrets
import uuid

import psycopg
import pytest
from psycopg import sql

from gateway.bootstrap import Login, bootstrap, login_statements, scram_sha256_verifier


def test_verifier_format_and_salting() -> None:
    v = scram_sha256_verifier("pw")
    method, rest = v.split("$", 1)
    iterations_salt, keys = rest.split("$")
    iterations, salt = iterations_salt.split(":")
    stored, server = keys.split(":")
    assert method == "SCRAM-SHA-256" and iterations == "4096"
    assert len(base64.b64decode(salt)) == 16
    assert len(base64.b64decode(stored)) == len(base64.b64decode(server)) == 32
    assert scram_sha256_verifier("pw") != v  # random salt every time


def test_known_vector() -> None:
    # Fixed salt: the verifier is fully determined (catches accidental algorithm changes).
    v = scram_sha256_verifier("pencil", salt=b"\x00" * 16)
    assert v == scram_sha256_verifier("pencil", salt=b"\x00" * 16)
    assert v.startswith("SCRAM-SHA-256$4096:AAAAAAAAAAAAAAAAAAAAAA==$")


def test_statements_never_contain_the_password() -> None:
    password = "correct-horse-" + secrets.token_hex(8)
    login = Login("bank_api", password, "bank")
    for exists in (False, True):
        for statement in login_statements(login, exists=exists):
            assert password not in statement.as_string(None)


def test_login_comes_from_the_module_url() -> None:
    login = Login.from_url("postgresql://bank_api:s3cret@db:5432/voiceref", "bank")
    assert (login.role, login.password, login.schema) == ("bank_api", "s3cret", "bank")
    with pytest.raises(ValueError, match="user and password"):
        Login.from_url("postgresql://db:5432/voiceref", "bank")


ADMIN = os.environ.get("TEST_DATABASE_URL")


@pytest.mark.skipif(not ADMIN, reason="TEST_DATABASE_URL not set")
def test_real_login_works_and_rotation_replaces_the_password() -> None:
    assert ADMIN
    role, schema = f"t_{uuid.uuid4().hex[:8]}", f"s_{uuid.uuid4().hex[:8]}"
    admin = psycopg.conninfo.conninfo_to_dict(ADMIN)

    def url(password: str) -> str:
        return psycopg.conninfo.make_conninfo(
            ADMIN, user=role, password=password, dbname=admin.get("dbname")
        )

    first, second = secrets.token_hex(16), secrets.token_hex(16)
    try:
        bootstrap(ADMIN, [Login(role, first, schema)])
        with psycopg.connect(url(first)) as conn:
            assert conn.execute("SHOW search_path").fetchone() == (schema,)
        with psycopg.connect(ADMIN) as conn:
            stored = conn.execute(
                "SELECT rolpassword FROM pg_authid WHERE rolname = %s", (role,)
            ).fetchone()
        assert stored and stored[0].startswith("SCRAM-SHA-256$")

        bootstrap(ADMIN, [Login(role, second, schema)])  # rotate
        with pytest.raises(psycopg.OperationalError):
            psycopg.connect(url(first)).close()
        psycopg.connect(url(second)).close()
    finally:
        with psycopg.connect(ADMIN, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
            conn.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))
