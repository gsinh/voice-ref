#!/usr/bin/env bash
# Local only: Postgres runs this once, when its volume is first created.
# Passwords come from the environment, never from the repo.
set -euo pipefail

: "${BANK_DB_PASSWORD:?BANK_DB_PASSWORD must be set}"
: "${ORCHESTRATOR_DB_PASSWORD:?ORCHESTRATOR_DB_PASSWORD must be set}"

psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v bank_pw="$BANK_DB_PASSWORD" -v orch_pw="$ORCHESTRATOR_DB_PASSWORD" \
  -f /bootstrap/bootstrap.sql
