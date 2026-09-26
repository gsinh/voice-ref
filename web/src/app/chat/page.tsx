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
              {ai ? `${ai.llm.model}${ai.llm.configured ? "" : " (no key)"}` : "unknown"}
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
      {!status.reachable && (
        <p role="alert" className="mt-4 rounded-md bg-amber-50 p-3 text-sm text-amber-800 dark:bg-amber-950 dark:text-amber-200">
          The backend is unreachable ({status.error}). Start it with <code>make up</code>.
        </p>
      )}
      <ChatClient />
    </main>
  );
}
