"""Create (or rotate) each module's database login and schema. The only admin step.

Security properties (ADR-0019):
- **No plaintext password is ever sent to Postgres.** The SCRAM-SHA-256 verifier is
  computed here, client-side, and sent in its place; Postgres stores a verifier as-is.
  So the password can't leak through server logs, `pg_stat_statements` or
  `pg_stat_activity`, which a plain `CREATE ROLE ... PASSWORD 'secret'` risks.
- **One source of truth.** Role name and password are read from each module's own
  database URL, the same value the module connects with. They cannot drift apart.
- **Idempotent and rotatable.** Running it again updates the password to whatever the
  URL now says: rotate a password by changing the secret and re-running bootstrap.
- Each role gets exactly one schema, owned by it, and nothing on `public`.

Works the same against the local container and Neon: run it wherever the admin URL is.
"""

import base64
import hashlib
import hmac
import logging
import os
from dataclasses import dataclass

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

log = logging.getLogger(__name__)

SCRAM_ITERATIONS = 4096  # Postgres' default scram_iterations


@dataclass(frozen=True)
class Login:
    role: str
    password: str
    schema: str

    @classmethod
    def from_url(cls, database_url: str, schema: str) -> "Login":
        params = conninfo_to_dict(database_url)
        role, password = params.get("user"), params.get("password")
        if not role or not password:
            raise ValueError(f"the database URL for schema {schema!r} needs a user and password")
        return cls(role=str(role), password=str(password), schema=schema)


def scram_sha256_verifier(
    password: str, *, salt: bytes | None = None, iterations: int = SCRAM_ITERATIONS
) -> str:
    """The SCRAM-SHA-256 verifier Postgres would store for this password (RFC 5802/7677).

    Format: SCRAM-SHA-256$<iterations>:<salt>$<StoredKey>:<ServerKey>, base64 parts.
    """
    salt = salt if salt is not None else os.urandom(16)
    salted = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    client_key = hmac.new(salted, b"Client Key", "sha256").digest()
    stored_key = hashlib.sha256(client_key).digest()
    server_key = hmac.new(salted, b"Server Key", "sha256").digest()

    def b64(raw: bytes) -> str:
        return base64.b64encode(raw).decode()

    return f"SCRAM-SHA-256${iterations}:{b64(salt)}${b64(stored_key)}:{b64(server_key)}"


def login_statements(login: Login, *, exists: bool) -> list[sql.Composed]:
    """The SQL for one login. Contains the verifier, never the password."""
    role, schema = sql.Identifier(login.role), sql.Identifier(login.schema)
    verifier = sql.Literal(scram_sha256_verifier(login.password))
    verb = sql.SQL("ALTER ROLE" if exists else "CREATE ROLE")
    return [
        sql.SQL("{} {} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}").format(
            verb, role, verifier
        ),
        sql.SQL("CREATE SCHEMA IF NOT EXISTS {} AUTHORIZATION {}").format(schema, role),
        sql.SQL("ALTER SCHEMA {} OWNER TO {}").format(schema, role),
        sql.SQL("ALTER ROLE {} SET search_path = {}").format(role, schema),
    ]


def bootstrap(admin_url: str, logins: list[Login]) -> None:
    with psycopg.connect(admin_url, autocommit=True) as conn:
        # Nobody gets to create objects in `public`; each module has its own schema.
        conn.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        for login in logins:
            row = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (login.role,))
            exists = row.fetchone() is not None
            with conn.transaction():
                for statement in login_statements(login, exists=exists):
                    conn.execute(statement)
            log.info(
                "login ready",
                extra={"role": login.role, "schema": login.schema, "rotated": exists},
            )
