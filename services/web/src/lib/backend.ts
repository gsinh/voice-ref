// Server-only: backend topology never reaches the browser (ADR-0011, BFF).
import "server-only";

export type ServiceStatus = {
  name: string;
  role: string;
  ready: boolean;
  detail: string;
  latencyMs: number;
};

type Service = { name: string; role: string; url: string };

// Internal URLs come from the runtime environment (12-factor), read per request.
function services(): Service[] {
  const env = process.env;
  return [
    { name: "orchestrator", role: "LangGraph conversation graph", url: env.ORCHESTRATOR_URL ?? "http://localhost:8000" },
    { name: "banking_api", role: "Mock bank system of record", url: env.BANKING_API_URL ?? "http://localhost:8001" },
    { name: "mcp_server", role: "MCP tool boundary", url: env.MCP_SERVER_URL ?? "http://localhost:8002" },
    { name: "decision", role: "Laya System-1 decisions", url: env.DECISION_URL ?? "http://localhost:8003" },
  ];
}

const TIMEOUT_MS = 2000;

async function probe(service: Service): Promise<ServiceStatus> {
  const started = performance.now();
  try {
    const res = await fetch(`${service.url}/readyz`, {
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    const body = (await res.json()) as { status: string; checks: Record<string, string> };
    const checks = Object.entries(body.checks)
      .map(([k, v]) => `${k}: ${v}`)
      .join(", ");
    return {
      ...service,
      ready: res.ok,
      detail: checks || "no dependencies",
      latencyMs: Math.round(performance.now() - started),
    };
  } catch (err) {
    return {
      ...service,
      ready: false,
      detail: err instanceof Error ? err.name : "unreachable",
      latencyMs: Math.round(performance.now() - started),
    };
  }
}

export async function systemStatus(): Promise<ServiceStatus[]> {
  return Promise.all(services().map(probe));
}
