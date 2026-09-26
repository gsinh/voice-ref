// Server-only: the backend's URL and token never reach the browser (ADR-0011, BFF).
import "server-only";

const DEFAULT_TIMEOUT_MS = 2000;

// Read per request from the runtime environment (12-factor), not inlined at build time.
function config() {
  return {
    url: process.env.BACKEND_URL ?? "http://localhost:7860",
    // Hugging Face token for the private Space in production; unset locally.
    token: process.env.BACKEND_TOKEN,
  };
}

/** Server-to-server call to the backend. The only way this app talks to it. */
export async function backendFetch(
  path: string,
  init: RequestInit = {},
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<Response> {
  const { url, token } = config();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return fetch(`${url}${path}`, {
    cache: "no-store",
    signal: AbortSignal.timeout(timeoutMs),
    ...init,
    headers,
  });
}

export type Check = { name: string; ok: boolean; detail: string };

export type AiStatus = {
  llm: {
    model: string;
    endpoint: string | null;
    configured: boolean;
    available?: boolean;
    problem?: string;
    offered?: string[];
  };
  system1: { enabled: boolean; reachable?: boolean; problem?: string };
};

export type BackendStatus = {
  reachable: boolean;
  ready: boolean;
  latencyMs: number;
  checks: Check[];
  modules: Record<string, string>;
  ai?: AiStatus;
  error?: string;
};

export async function backendStatus(): Promise<BackendStatus> {
  const started = performance.now();
  try {
    const [ready, root, ai] = await Promise.all([
      backendFetch("/readyz"),
      backendFetch("/"),
      backendFetch("/api/status"),
    ]);
    const readyBody = (await ready.json()) as { checks: Record<string, string> };
    const rootBody = (await root.json()) as { modules: Record<string, string> };
    const aiBody = ai.ok ? ((await ai.json()) as AiStatus) : undefined;
    return {
      reachable: true,
      ready: ready.ok,
      latencyMs: Math.round(performance.now() - started),
      checks: Object.entries(readyBody.checks).map(([name, v]) => ({
        name,
        ok: v === "ok",
        detail: v,
      })),
      modules: rootBody.modules,
      ai: aiBody,
    };
  } catch (err) {
    return {
      reachable: false,
      ready: false,
      latencyMs: Math.round(performance.now() - started),
      checks: [],
      modules: {},
      error: err instanceof Error ? err.name : "unreachable",
    };
  }
}
