# 0019. Secrets: never in SQL, never in environment dumps, never in the repo

- **Status:** Accepted
- **Date:** 2026-09-28

## Context
Security tooling flagged `CREATE ROLE bank_api LOGIN PASSWORD :'bank_pw'`. The warning
was right. A password sent inside a SQL statement can end up in the server log
(`log_statement`), in `pg_stat_statements`, in `pg_stat_activity` and in psql history.
Looking wider, secrets were also:
- passed to containers as environment variables, so visible to anyone who can run
  `docker inspect` or read `/proc/<pid>/environ`;
- given to containers that didn't need them (Postgres received the app logins' passwords);
- shipped as weak, committed placeholders (`change-me-...`) in `.env.example`;
- hard-coded in CI.

## Decision
1. **Postgres only ever receives SCRAM verifiers.** `python -m gateway bootstrap`
   computes each login's SCRAM-SHA-256 verifier client-side and sends that instead of
   the password; Postgres stores a verifier as-is. Verified with `log_statement=all`:
   30 statements logged, zero occurrences of any password.
2. **One source of truth per login.** Bootstrap reads each role and password from the
   module's own database URL, the value the module connects with. Re-running it
   rotates the password (`make rotate-db-passwords`).
3. **Secrets are files, not environment variables.** `make secrets` creates `./secrets/`
   (gitignored, `0700`) with strong random values, and compose mounts them as Docker
   secrets at `/run/secrets/<NAME>`. A shared settings convention (`config_kit`) reads
   them; environment variables still win, which is how Hugging Face Space and Cloudflare
   secrets arrive in production (12-factor stays intact).
4. **Least privilege per container.** Postgres gets only its admin password; only the
   one-off `migrate` job gets the admin login; the backend gets its module logins and
   API keys; the web BFF gets only the LiveKit credentials it needs to mint tokens.
5. **No committed credentials.** `.env.example` holds no secrets. CI generates random
   per-run credentials and masks them in logs.

## Alternatives considered
- **psql `\password`.** Also sends a verifier, but only interactively; not scriptable.
- **Keep env vars, tighten Docker access.** Env vars still leak into crash dumps, child
  processes and debug endpoints; files are the recognised pattern (Docker/Kubernetes
  secrets).
- **A secrets manager (Vault, Doppler, 1Password CLI).** Right for a real bank; more
  than a free-tier demo needs. The file convention maps onto any of them later.

## Consequences
- An existing local database keeps its old admin password: run `make db-reset` once
  (demo data is re-seeded automatically).
- Secret files are world-readable *inside* the private `0700` directory, because the
  containers run as different non-root users and Docker bind-mounts the files.
- At rest on a laptop, secrets are still files on disk. That is inherent; the gains are
  no leakage through SQL, logs, `docker inspect` or git, and no weak defaults.

## Principle
**Secrets are data with the smallest possible audience**: generated, not chosen;
delivered only to what needs them; never echoed into logs or statements.
