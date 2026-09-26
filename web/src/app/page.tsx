import Link from "next/link";
import { connection } from "next/server";

import { backendStatus } from "@/lib/backend";

const phases = [
  { n: 0, name: "Skeleton", detail: "Modular monolith, Postgres, CI, ADRs", done: true },
  { n: 1, name: "Core (text)", detail: "LangGraph, Laya, MCP, three use cases", done: true },
  { n: 2, name: "Voice", detail: "LiveKit Cloud, Silero VAD, Whisper, Kokoro", done: false },
  { n: 3, name: "Production traits", detail: "Tracing, faults, fallback, Kestra, memory", done: false },
  { n: 4, name: "Evaluation", detail: "Intent, tools, groundedness, compliance", done: false },
  { n: 5, name: "Ship", detail: "HF Spaces, Neon, Cloudflare Workers, demo", done: false },
];

export default async function Home() {
  // Render per request so status and env vars are read at runtime, not at build time.
  await connection();
  const status = await backendStatus();
  const summary = !status.reachable
    ? `Backend unreachable (${status.error})`
    : status.ready
      ? "Backend ready"
      : "Backend not ready";

  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-12 sm:px-6">
      <h1 className="text-3xl font-semibold tracking-tight">Enterprise Voice AI Reference</h1>
      <p className="mt-3 text-zinc-600 dark:text-zinc-400">
        A voice agent for a retail bank, built as an enterprise architecture problem: business
        outcomes, guardrails, latency, observability and cost.
      </p>

      <Link
        href="/chat"
        className="mt-6 inline-block rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white"
      >
        Try the text chat →
      </Link>

      <section className="mt-10">
        <div className="flex items-baseline justify-between gap-4">
          <h2 className="text-lg font-semibold">System status</h2>
          <span className={status.ready ? "text-emerald-600" : "text-amber-600"}>
            {summary} · {status.latencyMs} ms
          </span>
        </div>
        <p className="mt-1 text-sm text-zinc-500">
          Checked by this page&apos;s server on every request; the browser never calls the
          backend.
        </p>
        <ul className="mt-4 divide-y divide-zinc-200 rounded-lg border border-zinc-200 bg-white dark:divide-zinc-800 dark:border-zinc-800 dark:bg-zinc-900">
          {status.checks.map((c) => (
            <li key={c.name} className="flex items-center gap-3 px-4 py-3">
              <span
                aria-hidden
                className={`h-2.5 w-2.5 shrink-0 rounded-full ${c.ok ? "bg-emerald-500" : "bg-red-500"}`}
              />
              <p className="flex-1 font-mono text-sm">{c.name}</p>
              <span className="text-xs text-zinc-500">{c.detail}</span>
            </li>
          ))}
          {Object.entries(status.modules).map(([name, prefix]) => (
            <li key={name} className="flex items-center gap-3 px-4 py-3">
              <span aria-hidden className="h-2.5 w-2.5 shrink-0 rounded-full bg-zinc-400" />
              <p className="flex-1 font-mono text-sm">{name}</p>
              <span className="font-mono text-xs text-zinc-500">{prefix}</span>
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
