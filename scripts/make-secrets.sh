#!/usr/bin/env sh
# Create the local secrets directory (ADR-0019). Safe to re-run: existing values are kept.
#
#   secrets/            0700: only you can read it on this machine; gitignored
#     POSTGRES_PASSWORD           generated  database admin password
#     ADMIN_DATABASE_URL          generated  admin login, used only by `bootstrap`
#     BANK_DATABASE_URL           generated  bank module's own login
#     ORCHESTRATOR_DATABASE_URL   generated  orchestrator module's own login
#     TOKEN_SIGNING_KEY           generated  signs session/confirmation tokens
#     LLM_API_KEY                 yours      e.g. Groq key (gsk_...)
#     LIVEKIT_API_KEY             yours      from LiveKit Cloud (Phase 2, voice)
#     LIVEKIT_API_SECRET          yours
#
# Files are mounted into containers as Docker secrets at /run/secrets/<NAME>, so they
# never appear in environment variables, `docker inspect` or shell history.
# Files are world-readable *inside* the private directory because the containers run as
# different non-root users; the 0700 directory is what keeps them private on the host.
set -eu

dir="${1:-secrets}"
umask 077
mkdir -p "$dir"
chmod 700 "$dir"

random() {
  if command -v openssl >/dev/null 2>&1; then openssl rand -hex 32
  else python3 -c 'import secrets; print(secrets.token_hex(32))'; fi
}

# Value of NAME from .env, so keys you already put there move over automatically.
from_env_file() {
  [ -f .env ] || return 0
  sed -n "s/^$1=//p" .env | tail -n 1 | sed -e 's/^"//' -e 's/"$//'
}

write() {  # write NAME VALUE, unless NAME already has a value
  if [ -s "$dir/$1" ]; then echo "  kept      $1"; return; fi
  printf '%s' "$2" > "$dir/$1"
  chmod 644 "$dir/$1"
  if [ -n "$2" ]; then echo "  created   $1"; else echo "  empty     $1  (fill in yours)"; fi
}

pg="$(random)"; bank="$(random)"; orch="$(random)"
[ -s "$dir/POSTGRES_PASSWORD" ] && pg="$(cat "$dir/POSTGRES_PASSWORD")"

echo "Secrets in $dir/:"
write POSTGRES_PASSWORD "$pg"
write ADMIN_DATABASE_URL "postgresql://postgres:$pg@postgres:5432/voiceref"
write BANK_DATABASE_URL "postgresql://bank_api:$bank@postgres:5432/voiceref"
write ORCHESTRATOR_DATABASE_URL "postgresql://orchestrator:$orch@postgres:5432/voiceref"
write TOKEN_SIGNING_KEY "$(random)"
for name in LLM_API_KEY LIVEKIT_API_KEY LIVEKIT_API_SECRET; do
  write "$name" "$(from_env_file "$name")"
done

if [ -f .env ] && grep -Eq '^(POSTGRES_PASSWORD|BANK_DB_PASSWORD|ORCHESTRATOR_DB_PASSWORD|TOKEN_SIGNING_KEY|LLM_API_KEY|LIVEKIT_API_KEY|LIVEKIT_API_SECRET)=' .env; then
  echo
  echo "Now delete those secret lines from .env: they live in $dir/ instead."
fi
