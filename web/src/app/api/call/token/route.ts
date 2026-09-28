// BFF endpoint: mint a LiveKit token for a demo caller. The API secret never leaves the server.
import { DEMO_CALLERS } from "@/lib/chat";
import { livekitConfig, mintCallToken } from "@/lib/livekit";

export async function POST(request: Request) {
  if (!livekitConfig().configured) {
    return Response.json({ error: "voice is not configured (LiveKit)" }, { status: 503 });
  }
  let callerPhone: unknown;
  try {
    callerPhone = ((await request.json()) as { caller_phone?: unknown }).caller_phone;
  } catch {
    return Response.json({ error: "invalid JSON" }, { status: 400 });
  }
  // Only the demo callers: the browser must not be able to claim any caller ID it likes.
  if (!DEMO_CALLERS.some((c) => c.phone === callerPhone)) {
    return Response.json({ error: "unknown caller" }, { status: 400 });
  }
  return Response.json(await mintCallToken(callerPhone as string));
}
