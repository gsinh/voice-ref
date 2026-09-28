"""Entry point. Admin tasks are one-off processes of the same image (12-factor, XII):

python -m gateway start     # default: gateway + sidecars under the launcher
python -m gateway serve     # the HTTP server alone
python -m gateway bootstrap # create/rotate module logins + schemas (needs ADMIN_DATABASE_URL)
python -m gateway migrate   # apply each module's pending migrations
python -m gateway seed      # reset the synthetic demo data
python -m gateway bootstrap migrate seed   # several commands, in order
"""

import argparse
import asyncio
import logging

import uvicorn

import banking_api
import orchestrator
from gateway import launcher
from gateway.bootstrap import bootstrap
from gateway.composition import ModuleSettings, logins, migration_sets
from gateway.logging import configure_logging
from gateway.migrate import apply, run_script
from gateway.settings import Settings

log = logging.getLogger("gateway")

COMMANDS = ["start", "serve", "bootstrap", "migrate", "seed"]


def main() -> None:
    parser = argparse.ArgumentParser(prog="gateway")
    parser.add_argument("commands", nargs="*", metavar="command", help=f"one of {COMMANDS}")
    commands: list[str] = parser.parse_args().commands or ["start"]
    if unknown := [c for c in commands if c not in COMMANDS]:
        parser.error(f"unknown command(s) {unknown}; choose from {COMMANDS}")

    settings = Settings()
    configure_logging(settings.service_name, settings.log_level)
    modules = ModuleSettings.from_env()

    for command in commands:
        run_command(command, settings, modules)


def run_command(command: str, settings: Settings, modules: ModuleSettings) -> None:
    if command == "start":
        launcher.main()
    elif command == "serve":
        # Port binding (factor VII). Uvicorn drains in-flight requests on SIGTERM (factor IX).
        uvicorn.run(
            "gateway.app:create_app",
            factory=True,
            host=settings.host,
            port=settings.port,
            log_config=None,
            timeout_graceful_shutdown=10,
        )
    elif command == "bootstrap":
        if settings.admin_database_url is None:
            raise SystemExit("bootstrap needs ADMIN_DATABASE_URL (the database admin login)")
        bootstrap(settings.admin_database_url.get_secret_value(), logins(modules))
    elif command == "migrate":
        for ms in migration_sets(modules):
            applied = apply(ms)
            log.info("migrations up to date", extra={"component": ms.module, "applied": applied})
        # LangGraph owns its checkpoint tables; its setup() is idempotent.
        asyncio.run(orchestrator.setup_storage(modules.orchestrator.database_url))
        log.info("checkpoint storage ready", extra={"component": "orchestrator"})
    elif command == "seed":
        run_script(modules.bank.database_url, banking_api.SCHEMA, banking_api.SEED)
        log.info("demo data reset", extra={"component": "banking_api"})


if __name__ == "__main__":
    main()
