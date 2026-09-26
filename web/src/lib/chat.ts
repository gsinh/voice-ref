// Shared types and demo data for the chat page. Safe for the browser: no secrets here.

export type TurnEvent = {
  type: "decision" | "tool" | "llm" | "lookup";
  name?: string;
  question?: string;
  label?: string | null;
  confidence?: number | null;
  source?: "system1" | "llm" | "none";
  latency_ms: number;
  ok?: boolean;
  error?: string;
  notes?: string[];
  input_tokens?: number | null;
  output_tokens?: number | null;
};

export type ChatTurn = {
  conversation_id: string;
  reply: string;
  awaiting: "otp" | "card_choice" | "confirmation" | null;
  intent: string | null;
  authenticated: boolean;
  outcome: string | null;
  events: TurnEvent[];
  total_ms: number;
};

// Synthetic customers from the seed data. The phone number plays the role of caller ID.
export const DEMO_CALLERS = [
  { phone: "+919800000001", name: "Aarav Sharma", note: "₹1,999 charge yesterday, two cards" },
  { phone: "+919800000002", name: "Priya Nair", note: "prefers Hindi, one card" },
  { phone: "+919800000003", name: "Rohan Mehta", note: "current account, one card" },
] as const;

export const DEMO_OTP = "123456";

export const SUGGESTIONS = [
  "What's my balance?",
  "What is this ₹1,999 charge from yesterday?",
  "I've lost my debit card",
  "I want to talk to a person",
];
