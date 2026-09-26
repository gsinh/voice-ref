-- One-time bootstrap, run as the database admin. The only admin step (ADR-0007).
-- Creates one login role and one schema per module; each module's own migrations then
-- run as that role, so a module can only ever touch the schema it owns.
--
-- Local:  runs automatically on first start (infra/postgres/init/01-bootstrap.sh).
-- Neon:   psql "$NEON_ADMIN_URL" -v bank_pw=... -v orch_pw=... -f infra/postgres/bootstrap.sql

\set ON_ERROR_STOP on

REVOKE ALL ON SCHEMA public FROM PUBLIC;

CREATE ROLE bank_api LOGIN PASSWORD :'bank_pw';
CREATE SCHEMA bank AUTHORIZATION bank_api;
ALTER ROLE bank_api SET search_path = bank;

CREATE ROLE orchestrator LOGIN PASSWORD :'orch_pw';
CREATE SCHEMA orchestrator AUTHORIZATION orchestrator;
ALTER ROLE orchestrator SET search_path = orchestrator;
