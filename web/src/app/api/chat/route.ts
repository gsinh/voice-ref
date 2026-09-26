// BFF endpoint: the browser posts here; this server forwards to the private backend.
import { backendFetch } from "@/lib/backend";

const LLM_TURN_TIMEOUT_MS = 30_000;

type Body = { conversation_id?: unknown; caller_phone?: unknown; message?: unknown };

export async function POST(request: Request) {
  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return Response.json({ error: "invalid JSON" }, { status: 400 });
  }
  const { conversation_id, caller_phone, message } = body;
  if (typeof caller_phone !== "string" || typeof message !== "string" || !message.trim()) {
    return Response.json({ error: "caller_phone and message are required" }, { status: 400 });
  }

  try {
    const resp = await backendFetch(
      "/api/chat",
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          conversation_id: typeof conversation_id === "string" ? conversation_id : null,
          caller_phone,
          message: message.slice(0, 2000),
        }),
      },
      LLM_TURN_TIMEOUT_MS,
    );
    // Pass the backend's answer through, but never its internals on failure.
    if (!resp.ok) {
      return Response.json({ error: `backend error ${resp.status}` }, { status: 502 });
    }
    return Response.json(await resp.json());
  } catch (err) {
    const reason = err instanceof Error ? err.name : "unreachable";
    return Response.json({ error: `backend unreachable (${reason})` }, { status: 502 });
  }
}
