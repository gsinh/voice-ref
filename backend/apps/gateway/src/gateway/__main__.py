"""Entry point. Admin tasks are one-off processes of the same image (12-factor, XII):

python -m gateway serve     # default: run the HTTP server
python -m gateway migrate   # apply each module's pending migrations
python -m gateway seed      # reset the synthetic demo data
"""

import argparse
import logging

import uvicorn

import banking_api
from gateway.composition import ModuleSettings, migration_sets
from gateway.logging import configure_logging
from gateway.migrate import apply, run_script
from gateway.settings import Settings

log = logging.getLogger("gateway")

COMMANDS = ["serve", "migrate", "seed"]


def main() -> None:
    parser = argparse.ArgumentParser(prog="gateway")
    parser.add_argument("commands", nargs="*", metavar="command", help=f"one of {COMMANDS}")
    commands: list[str] = parser.parse_args().commands or ["serve"]
    if unknown := [c for c in commands if c not in COMMANDS]:
        parser.error(f"unknown command(s) {unknown}; choose from {COMMANDS}")

    settings = Settings()
    configure_logging(settings.service_name, settings.log_level)
    modules = ModuleSettings.from_env()

    for command in commands:
        run_command(command, settings, modules)


def run_command(command: str, settings: Settings, modules: ModuleSettings) -> None:
    if command == "serve":
        # Port binding (factor VII). Uvicorn drains in-flight requests on SIGTERM (factor IX).
        uvicorn.run(
            "gateway.app:create_app",
            factory=True,
            host=settings.host,
            port=settings.port,
            log_config=None,
            timeout_graceful_shutdown=10,
        )
    elif command == "migrate":
        for ms in migration_sets(modules):
            applied = apply(ms)
            log.info("migrations up to date", extra={"component": ms.module, "applied": applied})
    elif command == "seed":
        run_script(modules.bank.database_url, banking_api.SCHEMA, banking_api.SEED)
        log.info("demo data reset", extra={"component": "banking_api"})


if __name__ == "__main__":
    main()
