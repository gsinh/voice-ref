"""Wires the modules together. Adding a module means adding it here, nowhere else (OCP)."""

from dataclasses import dataclass

from fastapi import FastAPI

import banking_api
import mcp_server
import orchestrator
from gateway.bootstrap import Login
from gateway.health import ReadinessCheck, postgres_check
from gateway.migrate import MigrationSet


@dataclass(frozen=True)
class ModuleSettings:
    bank: banking_api.Settings
    orchestrator: orchestrator.Settings
    mcp: mcp_server.Settings

    @classmethod
    def from_env(cls) -> "ModuleSettings":
        return cls(
            bank=banking_api.Settings(),
            orchestrator=orchestrator.Settings(),
            mcp=mcp_server.Settings(),
        )


# URL prefix per module. The public API surface of the backend.
PREFIXES = {
    "orchestrator": "/api",
    "banking_api": "/bank",
    "mcp_server": "/mcp",
}


def build_mcp(ms: ModuleSettings) -> mcp_server.McpComponent:
    return mcp_server.create_mcp(ms.mcp)


def mount_modules(app: FastAPI, ms: ModuleSettings, mcp: mcp_server.McpComponent) -> None:
    app.include_router(orchestrator.create_router(ms.orchestrator), prefix=PREFIXES["orchestrator"])
    app.include_router(banking_api.create_router(ms.bank), prefix=PREFIXES["banking_api"])
    app.mount(PREFIXES["mcp_server"], mcp.app)


def readiness_checks(ms: ModuleSettings) -> dict[str, ReadinessCheck]:
    """The process's own hard dependencies: each module's database login."""
    return {
        "bank_db": postgres_check(ms.bank.database_url),
        "orchestrator_db": postgres_check(ms.orchestrator.database_url),
    }


def migration_sets(ms: ModuleSettings) -> list[MigrationSet]:
    """Each module migrates its own schema, logged in as its own role."""
    return [
        MigrationSet(
            module="banking_api",
            database_url=ms.bank.database_url,
            schema=banking_api.SCHEMA,
            directory=banking_api.MIGRATIONS,
        ),
    ]


def logins(ms: ModuleSettings) -> list[Login]:
    """Each data-owning module's login, read from the URL it connects with."""
    return [
        Login.from_url(ms.bank.database_url, banking_api.SCHEMA),
        Login.from_url(ms.orchestrator.database_url, "orchestrator"),
    ]
