import { connection } from "next/server";

import { systemStatus } from "@/lib/backend";

const phases = [
  { n: 0, name: "Skeleton", detail: "Services, Postgres, CI, ADRs", done: true },
  { n: 1, name: "Core (text)", detail: "LangGraph, Laya, MCP, three use cases", done: false },
  { n: 2, name: "Voice", detail: "LiveKit Cloud, Silero VAD, Whisper, Kokoro", done: false },
  { n: 3, name: "Production traits", detail: "Tracing, faults, fallback, Kestra, memory", done: false },
  { n: 4, name: "Evaluation", detail: "Intent, tools, groundedness, compliance", done: false },
  { n: 5, name: "Ship", detail: "Hetzner, Cloudflare Tunnel, demo", done: false },
];

export default async function Home() {
  // Render per request so status and env vars are read at runtime, not at build time.
  await connection();
  const statuses = await systemStatus();
  const allReady = statuses.every((s) => s.ready);

  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-12 sm:px-6">
      <h1 className="text-3xl font-semibold tracking-tight">Enterprise Voice AI Reference</h1>
      <p className="mt-3 text-zinc-600 dark:text-zinc-400">
        A voice agent for a retail bank, built as an enterprise architecture problem: business
        outcomes, guardrails, latency, observability and cost.
      </p>

      <section className="mt-10">
        <div className="flex items-baseline justify-between">
          <h2 className="text-lg font-semibold">System status</h2>
          <span className={allReady ? "text-emerald-600" : "text-amber-600"}>
            {allReady ? "All services ready" : "Some services not ready"}
          </span>
        </div>
        <p className="mt-1 text-sm text-zinc-500">
          Checked server-side by this page on every request; the browser never calls the backends.
        </p>
        <ul className="mt-4 divide-y divide-zinc-200 rounded-lg border border-zinc-200 bg-white dark:divide-zinc-800 dark:border-zinc-800 dark:bg-zinc-900">
          {statuses.map((s) => (
            <li key={s.name} className="flex items-center gap-3 px-4 py-3">
              <span
                aria-hidden
                className={`h-2.5 w-2.5 shrink-0 rounded-full ${s.ready ? "bg-emerald-500" : "bg-red-500"}`}
              />
              <div className="min-w-0 flex-1">
                <p className="font-mono text-sm">{s.name}</p>
                <p className="truncate text-xs text-zinc-500">
                  {s.role} · {s.detail}
                </p>
              </div>
              <span className="text-xs tabular-nums text-zinc-500">{s.latencyMs} ms</span>
              <span className="sr-only">{s.ready ? "ready" : "not ready"}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-10">
        <h2 className="text-lg font-semibold">Build phases</h2>
        <ol className="mt-4 space-y-2">
          {phases.map((p) => (
            <li key={p.n} className="flex gap-3 text-sm">
              <span className="w-16 shrink-0 font-mono text-zinc-500">Phase {p.n}</span>
              <span className={p.done ? "font-medium" : ""}>
                {p.name} {p.done ? "✓" : ""}
              </span>
              <span className="text-zinc-500">— {p.detail}</span>
            </li>
          ))}
        </ol>
      </section>
    </main>
  );
}
