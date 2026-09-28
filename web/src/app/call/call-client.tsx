"use client";

import {
  LiveKitRoom,
  RoomAudioRenderer,
  useDataChannel,
  useTranscriptions,
  useVoiceAssistant,
} from "@livekit/components-react";
import { useState } from "react";

import { DEMO_CALLERS, DEMO_OTP } from "@/lib/chat";

type Connection = { serverUrl: string; participantToken: string; roomName: string };

type TurnMetrics = {
  stages: {
    end_of_utterance_ms: number;
    orchestrator_ms: number;
    tts_first_audio_ms: number | null;
  };
  interrupted: boolean;
  total_ms: number;
  intent: string | null;
  awaiting: string | null;
  outcome: string | null;
  authenticated: boolean | null;
  events: { type: string; name?: string; question?: string; label?: string | null; source?: string; latency_ms: number }[];
};

export default function CallClient() {
  const [caller, setCaller] = useState<string>(DEMO_CALLERS[0].phone);
  const [conn, setConn] = useState<Connection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  async function start() {
    setStarting(true);
    setError(null);
    try {
      const resp = await fetch("/api/call/token", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ caller_phone: caller }),
      });
      const data = (await resp.json()) as Connection & { error?: string };
      if (!resp.ok || data.error) throw new Error(data.error ?? `HTTP ${resp.status}`);
      setConn(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "could not start the call");
    } finally {
      setStarting(false);
    }
  }

  if (!conn) {
    return (
      <section className="mt-6 flex max-w-2xl flex-col gap-3 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
        <label htmlFor="caller" className="text-sm text-zinc-500">
          Calling as (caller ID)
        </label>
        <select
          id="caller"
          value={caller}
          onChange={(e) => setCaller(e.target.value)}
          className="min-w-0 max-w-full rounded-md border border-zinc-300 bg-transparent px-2 py-1 text-sm dark:border-zinc-700"
        >
          {DEMO_CALLERS.map((c) => (
            <option key={c.phone} value={c.phone}>
              {c.name} · {c.note}
            </option>
          ))}
        </select>
        <p className="text-sm text-zinc-500">
          Try: &ldquo;What&apos;s my balance?&rdquo;, then say the code{" "}
          <span className="font-mono">{DEMO_OTP.split("").join(" ")}</span>.
        </p>
        <button
          type="button"
          onClick={start}
          disabled={starting}
          className="self-start rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {starting ? "Connecting…" : "Start call"}
        </button>
        {error && (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        )}
      </section>
    );
  }

  return (
    <LiveKitRoom
      serverUrl={conn.serverUrl}
      token={conn.participantToken}
      connect
      audio
      video={false}
      onDisconnected={() => setConn(null)}
      className="mt-6 flex flex-1 flex-col"
    >
      <RoomAudioRenderer />
      <InCall onHangUp={() => setConn(null)} />
    </LiveKitRoom>
  );
}

const STATE_LABEL: Record<string, string> = {
  connecting: "Connecting…",
  initializing: "Agent joining…",
  listening: "Listening",
  thinking: "Thinking",
  speaking: "Speaking",
  disconnected: "Disconnected",
  failed: "Agent failed to join",
};

function InCall({ onHangUp }: { onHangUp: () => void }) {
  const { state, agent } = useVoiceAssistant();
  const transcripts = useTranscriptions();
  const [turns, setTurns] = useState<TurnMetrics[]>([]);

  useDataChannel("turn-metrics", (msg) => {
    try {
      const turn = JSON.parse(new TextDecoder().decode(msg.payload)) as TurnMetrics;
      setTurns((t) => [...t, turn].slice(-10));
    } catch {
      // ignore malformed metrics; they are best-effort
    }
  });

  const last = turns.at(-1);

  return (
    <div className="grid flex-1 grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
      <section aria-label="Call" className="flex min-h-[26rem] flex-col rounded-lg border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
        <div className="flex items-center gap-3 border-b border-zinc-200 p-3 dark:border-zinc-800">
          <span
            aria-hidden
            className={`h-3 w-3 rounded-full ${
              state === "speaking"
                ? "animate-pulse bg-indigo-500"
                : state === "listening"
                  ? "bg-emerald-500"
                  : state === "thinking"
                    ? "animate-pulse bg-amber-500"
                    : "bg-zinc-400"
            }`}
          />
          <p className="text-sm font-medium" aria-live="polite">
            {STATE_LABEL[state] ?? state}
          </p>
          <button
            type="button"
            onClick={onHangUp}
            className="ml-auto rounded-md bg-red-600 px-3 py-1.5 text-sm font-medium text-white"
          >
            Hang up
          </button>
        </div>
        <ol className="flex-1 space-y-3 overflow-y-auto p-4" aria-live="polite">
          {transcripts.length === 0 && (
            <li className="text-sm text-zinc-500">The transcript appears here as you talk.</li>
          )}
          {transcripts.map((t) => {
            const fromAgent = agent !== undefined && t.participantInfo.identity === agent.identity;
            return (
              <li key={t.streamInfo.id} className={fromAgent ? "flex" : "flex justify-end"}>
                <p
                  className={
                    fromAgent
                      ? "max-w-[80%] rounded-2xl rounded-bl-sm bg-zinc-100 px-3 py-2 text-sm dark:bg-zinc-800"
                      : "max-w-[80%] rounded-2xl rounded-br-sm bg-indigo-600 px-3 py-2 text-sm text-white"
                  }
                >
                  {t.text}
                </p>
              </li>
            );
          })}
        </ol>
      </section>

      <aside aria-label="Last turn" className="rounded-lg border border-zinc-200 bg-white p-4 text-sm dark:border-zinc-800 dark:bg-zinc-900">
        <h2 className="font-semibold">Last turn</h2>
        {!last ? (
          <p className="mt-2 text-zinc-500">
            After each reply: where the time went, from you stopping speaking to the agent&apos;s
            first sound.
          </p>
        ) : (
          <>
            <p className="mt-3 text-2xl font-semibold tabular-nums">{last.total_ms} ms</p>
            <p className="text-xs text-zinc-500">
              {last.interrupted
                ? "you spoke before the agent's first audio (barge-in)"
                : "voice-to-voice, before network to your ear"}
            </p>
            <ul className="mt-3 space-y-2">
              <Stage label="End of your turn (VAD + transcript)" ms={last.stages.end_of_utterance_ms} total={last.total_ms} />
              <Stage label="Orchestrator (decisions, tools, LLM)" ms={last.stages.orchestrator_ms} total={last.total_ms} />
              <Stage label="Speech synthesis, first audio" ms={last.stages.tts_first_audio_ms} total={last.total_ms} />
            </ul>
            <dl className="mt-4 grid grid-cols-2 gap-2">
              <div>
                <dt className="text-xs text-zinc-500">Intent</dt>
                <dd className="font-mono">{last.intent ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-xs text-zinc-500">Outcome</dt>
                <dd className="font-mono">{last.outcome ?? (last.awaiting ? `awaiting ${last.awaiting}` : "—")}</dd>
              </div>
            </dl>
            <ol className="mt-3 space-y-1 text-xs text-zinc-500">
              {last.events.map((e, i) => (
                <li key={i}>
                  {e.type === "decision"
                    ? `decide ${e.question}: ${e.label ?? "unsure"} (${e.source})`
                    : `${e.type} ${e.name ?? ""}`}{" "}
                  · {Math.round(e.latency_ms)} ms
                </li>
              ))}
            </ol>
          </>
        )}
      </aside>
    </div>
  );
}

function Stage({ label, ms, total }: { label: string; ms: number | null; total: number }) {
  const pct = ms !== null && total > 0 ? Math.max(2, Math.round((ms / total) * 100)) : 0;
  return (
    <li>
      <div className="flex justify-between gap-2">
        <span>{label}</span>
        <span className="tabular-nums text-zinc-500">{ms === null ? "interrupted" : `${ms} ms`}</span>
      </div>
      <div className="mt-1 h-1.5 rounded bg-zinc-100 dark:bg-zinc-800">
        <div className="h-1.5 rounded bg-indigo-500" style={{ width: `${pct}%` }} />
      </div>
    </li>
  );
}
