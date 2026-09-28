// Server-only: LiveKit configuration and call tokens for the /call page (ADR-0018).
import "server-only";

import { AccessToken, RoomAgentDispatch, RoomConfiguration } from "livekit-server-sdk";

import { readSecret } from "@/lib/secrets";

const TOKEN_TTL = "15m";

export function livekitConfig() {
  const url = process.env.LIVEKIT_URL ?? "";
  const apiKey = readSecret("LIVEKIT_API_KEY");
  const apiSecret = readSecret("LIVEKIT_API_SECRET");
  const agentName = process.env.LIVEKIT_AGENT_NAME || "bank-agent";
  return { url, apiKey, apiSecret, agentName, configured: Boolean(url && apiKey && apiSecret) };
}

/**
 * A token for one caller in a fresh room, with the bank agent dispatched into it.
 *
 * The caller's phone number is a participant *attribute* set here, server-side: it plays
 * the role of caller ID on a phone line. The agent trusts it; nothing the caller says or
 * does in the browser can change it.
 */
export async function mintCallToken(callerPhone: string) {
  const cfg = livekitConfig();
  const roomName = `call-${crypto.randomUUID()}`;
  const identity = `caller-${crypto.randomUUID().slice(0, 8)}`;
  const at = new AccessToken(cfg.apiKey, cfg.apiSecret, {
    identity,
    ttl: TOKEN_TTL,
    attributes: { caller_phone: callerPhone },
  });
  at.addGrant({
    room: roomName,
    roomJoin: true,
    canPublish: true, // microphone
    canSubscribe: true, // the agent's voice
    canPublishData: false, // callers have no reason to send data messages
  });
  at.roomConfig = new RoomConfiguration({
    agents: [new RoomAgentDispatch({ agentName: cfg.agentName })],
  });
  return { serverUrl: cfg.url, participantToken: await at.toJwt(), roomName };
}
