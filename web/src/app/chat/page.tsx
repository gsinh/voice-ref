import type { Metadata } from "next";
import Link from "next/link";
import { connection } from "next/server";

import { backendStatus } from "@/lib/backend";

import ChatClient from "./chat-client";

export const metadata: Metadata = { title: "Text chat · Enterprise Voice AI Reference" };

export default async function ChatPage() {
  await connection(); // read status at request time
  const status = await backendStatus();
  const ai = status.ai;

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 py-6 sm:px-6">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <Link href="/" className="text-sm text-zinc-500 hover:underline">
            ← Overview
          </Link>
          <h1 className="text-2xl font-semibold tracking-tight">Text chat</h1>
          <p className="text-sm text-zinc-500">
            The same conversation graph the voice agent will use, driven by text.
          </p>
        </div>
        <dl className="flex gap-4 text-xs text-zinc-500">
          <div>
            <dt className="uppercase tracking-wide">System 2</dt>
            <dd className="font-mono text-zinc-800 dark:text-zinc-200">
              {!ai
                ? "unknown"
                : `${ai.llm.model}${!ai.llm.configured ? " (no key)" : ai.llm.available === false ? " (unavailable)" : ""}`}
            </dd>
          </div>
          <div>
            <dt className="uppercase tracking-wide">System 1</dt>
            <dd className="font-mono text-zinc-800 dark:text-zinc-200">
              {!ai
                ? "unknown"
                : !ai.system1.enabled
                  ? "off (LLM decides)"
                  : ai.system1.reachable
                    ? "Laya ready"
                    : "unreachable → LLM fallback"}
            </dd>
          </div>
        </dl>
      </header>
      {ai?.llm.available === false && (
        <div role="alert" className="mt-4 rounded-md bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950 dark:text-amber-100">
          <p>
            <strong>System 2 can&apos;t be used:</strong> <code>{ai.llm.model}</code> at{" "}
            {ai.llm.endpoint}: {ai.llm.problem}. Set <code>LLM_MODEL</code> in <code>.env</code>{" "}
            and restart the backend.
          </p>
          {ai.llm.offered && ai.llm.offered.length > 0 && (
            <p className="mt-1 break-words text-xs">
              Offered: <code>{ai.llm.offered.join(", ")}</code>
            </p>
          )}
        </div>
      )}
      {ai?.system1.enabled && ai.system1.reachable === false && (
        <p className="mt-2 text-xs text-zinc-500">
          System 1 (Laya) is {ai.system1.problem}. Decisions fall back to the LLM meanwhile;
          check <code>docker compose logs backend</code>.
        </p>
      )}
      {!status.reachable && (
        <p role="alert" className="mt-4 rounded-md bg-amber-50 p-3 text-sm text-amber-800 dark:bg-amber-950 dark:text-amber-200">
          The backend is unreachable ({status.error}). Start it with <code>make up</code>.
        </p>
      )}
      <ChatClient />
    </main>
  );
}
