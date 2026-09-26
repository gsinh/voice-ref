"use client";

import { useRef, useState } from "react";

import {
  type ChatTurn,
  DEMO_CALLERS,
  DEMO_OTP,
  SUGGESTIONS,
  type TurnEvent,
} from "@/lib/chat";

type Line = { role: "customer" | "assistant" | "error"; text: string };

const AWAITING_LABEL: Record<string, string> = {
  otp: "Waiting for the one-time code",
  card_choice: "Waiting for which card",
  confirmation: "Waiting for explicit confirmation",
};

export default function ChatClient() {
  const [caller, setCaller] = useState<string>(DEMO_CALLERS[0].phone);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [lines, setLines] = useState<Line[]>([]);
  const [turn, setTurn] = useState<ChatTurn | null>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  function reset(phone = caller) {
    setCaller(phone);
    setConversationId(null);
    setLines([]);
    setTurn(null);
  }

  async function send(text: string) {
    const message = text.trim();
    if (!message || busy) return;
    const shown = turn?.awaiting === "otp" ? "•".repeat(message.length) : message;
    setLines((l) => [...l, { role: "customer", text: shown }]);
    setInput("");
    setBusy(true);
    try {
      const resp = await fetch("/api/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ conversation_id: conversationId, caller_phone: caller, message }),
      });
      const data = (await resp.json()) as ChatTurn & { error?: string };
      if (!resp.ok || data.error) throw new Error(data.error ?? `HTTP ${resp.status}`);
      setConversationId(data.conversation_id);
      setTurn(data);
      setLines((l) => [...l, { role: "assistant", text: data.reply }]);
    } catch (err) {
      setLines((l) => [...l, { role: "error", text: err instanceof Error ? err.message : "failed" }]);
    } finally {
      setBusy(false);
      requestAnimationFrame(() => endRef.current?.scrollIntoView({ behavior: "smooth" }));
    }
  }

  return (
    <div className="mt-6 grid flex-1 grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
      <section aria-label="Conversation" className="flex min-h-[28rem] flex-col rounded-lg border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
        <div className="flex flex-wrap items-center gap-2 border-b border-zinc-200 p-3 dark:border-zinc-800">
          <label htmlFor="caller" className="text-sm text-zinc-500">
            Calling as
          </label>
          <select
            id="caller"
            value={caller}
            onChange={(e) => reset(e.target.value)}
            className="min-w-0 max-w-full flex-1 rounded-md border border-zinc-300 bg-transparent px-2 py-1 text-sm sm:flex-none dark:border-zinc-700"
          >
            {DEMO_CALLERS.map((c) => (
              <option key={c.phone} value={c.phone}>
                {c.name} · {c.note}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => reset()}
            className="ml-auto rounded-md px-2 py-1 text-sm text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
          >
            New conversation
          </button>
        </div>

        <ol className="flex-1 space-y-3 overflow-y-auto p-4" aria-live="polite">
          {lines.length === 0 && (
            <li className="text-sm text-zinc-500">
              Say what a caller would say. The demo one-time code is{" "}
              <code className="font-mono">{DEMO_OTP}</code>.
            </li>
          )}
          {lines.map((line, i) => (
            <li key={i} className={line.role === "customer" ? "flex justify-end" : "flex"}>
              <p
                className={
                  line.role === "customer"
                    ? "max-w-[80%] rounded-2xl rounded-br-sm bg-indigo-600 px-3 py-2 text-sm text-white"
                    : line.role === "error"
                      ? "max-w-[80%] rounded-2xl bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300"
                      : "max-w-[80%] rounded-2xl rounded-bl-sm bg-zinc-100 px-3 py-2 text-sm dark:bg-zinc-800"
                }
              >
                {line.text}
              </p>
            </li>
          ))}
          {busy && <li className="text-sm text-zinc-500">…</li>}
          <div ref={endRef} />
        </ol>

        <div className="border-t border-zinc-200 p-3 dark:border-zinc-800">
          {lines.length === 0 && (
            <div className="mb-2 flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => send(s)}
                  className="rounded-full border border-zinc-300 px-3 py-1 text-xs hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800"
                >
                  {s}
                </button>
              ))}
            </div>
          )}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void send(input);
            }}
            className="flex gap-2"
          >
            <label htmlFor="message" className="sr-only">
              Message
            </label>
            <input
              id="message"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={turn?.awaiting === "otp" ? `One-time code (demo: ${DEMO_OTP})` : "Type what the caller says…"}
              autoComplete="off"
              inputMode={turn?.awaiting === "otp" ? "numeric" : "text"}
              className="min-w-0 flex-1 rounded-md border border-zinc-300 bg-transparent px-3 py-2 text-sm dark:border-zinc-700"
            />
            <button
              type="submit"
              disabled={busy || !input.trim()}
              className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              Send
            </button>
          </form>
        </div>
      </section>

      <TurnInspector turn={turn} />
    </div>
  );
}

function TurnInspector({ turn }: { turn: ChatTurn | null }) {
  return (
    <aside aria-label="Last turn" className="rounded-lg border border-zinc-200 bg-white p-4 text-sm dark:border-zinc-800 dark:bg-zinc-900">
      <h2 className="font-semibold">Last turn</h2>
      {!turn ? (
        <p className="mt-2 text-zinc-500">
          Each reply shows what the system decided, who decided it, which tools ran, and where
          the time went.
        </p>
      ) : (
        <>
          <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2">
            <Field label="Intent" value={turn.intent ?? "—"} />
            <Field label="Verified" value={turn.authenticated ? "yes" : "no"} />
            <Field label="Outcome" value={turn.outcome ?? "in progress"} />
            <Field label="Total" value={`${Math.round(turn.total_ms)} ms`} />
          </dl>
          {turn.awaiting && (
            <p className="mt-3 rounded-md bg-indigo-50 px-2 py-1 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-200">
              {AWAITING_LABEL[turn.awaiting] ?? turn.awaiting}
            </p>
          )}
          <h3 className="mt-4 text-xs font-semibold uppercase tracking-wide text-zinc-500">Trace</h3>
          <ol className="mt-2 space-y-2">
            {turn.events.map((e, i) => (
              <EventRow key={i} event={e} />
            ))}
          </ol>
        </>
      )}
    </aside>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-zinc-500">{label}</dt>
      <dd className="font-mono">{value}</dd>
    </div>
  );
}

function EventRow({ event: e }: { event: TurnEvent }) {
  const ms = `${Math.round(e.latency_ms)} ms`;
  if (e.type === "decision") {
    const who = e.source === "system1" ? "Laya" : e.source === "llm" ? "LLM" : "nobody sure";
    const conf = e.confidence != null ? ` @ ${e.confidence.toFixed(2)}` : "";
    return (
      <li>
        <p>
          <span className="text-zinc-500">decide {e.question}:</span>{" "}
          <span className="font-mono">{e.label ?? "unsure"}</span>{" "}
          <span className="text-zinc-500">
            by {who}
            {conf} · {ms}
          </span>
        </p>
        {e.notes?.map((n, i) => (
          <p key={i} className="pl-3 text-xs text-zinc-500">
            {n}
          </p>
        ))}
      </li>
    );
  }
  const tokens =
    e.type === "llm" && e.input_tokens != null ? ` · ${e.input_tokens}→${e.output_tokens} tok` : "";
  return (
    <li className={e.ok === false ? "text-red-600" : ""}>
      <span className="text-zinc-500">{e.type}</span> <span className="font-mono">{e.name}</span>{" "}
      <span className="text-zinc-500">
        · {ms}
        {tokens}
        {e.error ? ` · ${e.error}` : ""}
      </span>
    </li>
  );
}
