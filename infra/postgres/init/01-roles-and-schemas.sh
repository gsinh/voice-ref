#!/usr/bin/env bash
# Runs once, when the Postgres volume is first created (docker-entrypoint-initdb.d).
# One database, one schema + one login role per service (ADR-0007): each service can
# only touch what it owns. Passwords come from the environment, never from the repo.
set -euo pipefail

: "${BANK_DB_PASSWORD:?BANK_DB_PASSWORD must be set}"
: "${ORCHESTRATOR_DB_PASSWORD:?ORCHESTRATOR_DB_PASSWORD must be set}"

psql -v ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v bank_pw="$BANK_DB_PASSWORD" -v orch_pw="$ORCHESTRATOR_DB_PASSWORD" <<'SQL'
REVOKE ALL ON SCHEMA public FROM PUBLIC;

CREATE ROLE bank_api LOGIN PASSWORD :'bank_pw';
CREATE SCHEMA bank AUTHORIZATION bank_api;
ALTER ROLE bank_api SET search_path = bank;

CREATE ROLE orchestrator LOGIN PASSWORD :'orch_pw';
CREATE SCHEMA orchestrator AUTHORIZATION orchestrator;
ALTER ROLE orchestrator SET search_path = orchestrator;
SQL
