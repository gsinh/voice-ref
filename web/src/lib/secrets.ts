// Server-only: read a secret the same way the backend does (ADR-0019).
// 1. an environment variable, if non-empty (Cloudflare/Vercel secrets arrive this way);
// 2. otherwise the Docker secret file SECRETS_DIR/NAME (compose mounts /run/secrets).
import "server-only";

import { readFileSync } from "node:fs";
import { join } from "node:path";

export function readSecret(name: string): string {
  const fromEnv = process.env[name];
  if (fromEnv) return fromEnv;
  try {
    return readFileSync(join(process.env.SECRETS_DIR ?? "/run/secrets", name), "utf8").trim();
  } catch {
    return "";
  }
}
