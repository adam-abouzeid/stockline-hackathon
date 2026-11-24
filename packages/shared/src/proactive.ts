/** Proactive calls (GET /api/proactive/*): the voice agent phones a client first only to solve a problem on an order it already has.
 *  Mirrors apps/backend/app/schemas/proactive.py. */
import type { Id } from "./domain";

/** The only reason to phone: a client's open order cannot be delivered as planned. */
export type OpportunityType = "order_issue";
/** stock = a product is short (supplier shortage or not enough stock); delivery = no route serves the zone on that day. */
export type IssueKind = "stock" | "delivery";

export interface ProactiveOpportunity {
  id: string; // "order_issue~<clientId>~<orderId>"
  type: OpportunityType;
  priority: number; // higher = call first (driven by how close the delivery is)
  clientId: Id;
  clientName: string;
  contactName?: string;
  title: string; // the problem, in one line
  reason: string;
  facts: string[]; // the verified facts the agent may quote
  objective: string; // what the agent does on the call
  kinds: IssueKind[];
  deadline: string; // e.g. "Livraison aujourd'hui : à prévenir avant le départ du camion"
  productIds: Id[];
  orderId?: Id;
  orderValue: number; // the order's total excl. VAT: same urgency, the bigger order is called first
}

export type CallStatus = "ringing" | "answered" | "declined" | "missed" | "cancelled";
/** simulator = the web app plays the client's phone; phone = a real call to the demo number through Twilio (PHONE_MODE=twilio). */
export type CallChannel = "simulator" | "phone";

/** A call the agent decided to place by itself: it rings on the client's side until picked up, declined or missed. */
export interface ProactiveCall {
  id: string;
  opportunityId: string;
  clientId: Id;
  clientName: string;
  contactName?: string;
  type: OpportunityType;
  title: string;
  reason: string;
  deadline: string;
  priority: number;
  status: CallStatus;
  channel: CallChannel;
  orderId?: Id;
  createdAt: string;
  endedAt?: string; // when it stopped ringing
  hungUpAt?: string; // phone: when an answered call hung up
  note?: string; // why it did not ring / was cancelled
  outcome?: string; // what was decided on the call (tool record_call_outcome)
}

export interface DispatchResult {
  status: "ringing" | "nothing";
  call?: ProactiveCall;
}

export interface AutodialState {
  enabled: boolean;
  intervalSeconds: number;
  ringSeconds: number;
  cooldownSeconds: number;
  minPriority: number;
  ringing: number;
  phoneMode: "simulator" | "twilio";
}

/** GET /ai/phone/config: can a real phone ring? */
export interface PhoneConfig {
  mode: "simulator" | "twilio";
  ready: boolean;
  problems: string[];
  demoNumber: string; // masked
  publicUrl: string;
  activeCallId?: string | null;
}

/** GET /ai/phone/live (Server-Sent Events): one event of a real phone call, for the « Appel en cours » panel. */
export type PhoneLiveEvent = { callId: string; at: number } & (
  | { type: "call"; status: "dialling" | "ringing" | "answered" | "voicemail" | "ended"; clientName?: string; contactName?: string; title?: string;
      orderId?: string; opportunityId?: string; to?: string; result?: string; note?: string; durationS?: number; dialToAnswerMs?: number }
  | { type: "transcript"; track: "caller"; text: string; final: boolean; ignored?: boolean; stable?: string }
  | { type: "agent_text"; delta: string }
  | { type: "agent_tool"; name: string; args?: Record<string, unknown>; ok?: boolean; ms?: number }
  | { type: "agent_done"; text: string; timings?: Record<string, number> }
  | { type: "latency"; pickupToFirstAudioMs: number }
  | { type: "barge_in"; text: string }
  | { type: "hangup"; note: string }
  | { type: "error"; message: string }
  | { type: "agent_audio_start" | "agent_audio_end" | "twilio" | "amd"; [k: string]: unknown }
);

export interface ProactiveBrief extends ProactiveOpportunity {
  brief: string; // the full instructions given to the agent for the call
}
