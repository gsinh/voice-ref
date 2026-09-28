import type { Metadata } from "next";
import Link from "next/link";
import { connection } from "next/server";

import { livekitConfig } from "@/lib/livekit";

import CallClient from "./call-client";

export const metadata: Metadata = { title: "Voice call · Enterprise Voice AI Reference" };

export default async function CallPage() {
  await connection(); // configuration is read at request time
  const { configured } = livekitConfig();

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 py-6 sm:px-6">
      <Link href="/" className="text-sm text-zinc-500 hover:underline">
        ← Overview
      </Link>
      <h1 className="text-2xl font-semibold tracking-tight">Voice call</h1>
      <p className="text-sm text-zinc-500">
        Speak to the agent. Audio goes through LiveKit; every turn runs the same conversation
        graph as the text chat.
      </p>
      {configured ? (
        <CallClient />
      ) : (
        <section className="mt-6 max-w-2xl rounded-lg border border-zinc-200 bg-white p-4 text-sm dark:border-zinc-800 dark:bg-zinc-900">
          <h2 className="font-semibold">Voice isn&apos;t set up yet</h2>
          <ol className="mt-2 list-decimal space-y-1 pl-5">
            <li>
              Create a project on LiveKit Cloud and put its key and secret in{" "}
              <code>secrets/LIVEKIT_API_KEY</code> and <code>secrets/LIVEKIT_API_SECRET</code>.
            </li>
            <li>
              In <code>.env</code> set <code>LIVEKIT_URL=wss://&lt;project&gt;.livekit.cloud</code>{" "}
              and add the voice worker: <code>SIDECARS=laya,voice</code>.
            </li>
            <li>
              Run <code>make up</code> and reload this page.
            </li>
          </ol>
        </section>
      )}
    </main>
  );
}
