/** Proactive calls (GET /api/proactive/*): occasions where the voice agent should phone a client first. Mirrors apps/backend/app/schemas/proactive.py. */
import type { Id } from "./domain";

export type OpportunityType = "shortage_order" | "shortage_heads_up" | "overdue" | "seasonal";

export interface ProactiveOpportunity {
  id: string; // "<type>~<clientId>~<key>"
  type: OpportunityType;
  priority: number; // higher = call first
  clientId: Id;
  clientName: string;
  contactName?: string;
  title: string;
  reason: string;
  facts: string[]; // the verified facts the agent may quote
  objective: string;
  productIds: Id[];
  orderId?: Id;
}

export type CallStatus = "ringing" | "answered" | "declined" | "missed";

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
  priority: number;
  status: CallStatus;
  createdAt: string;
  endedAt?: string;
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
}

export interface ProactiveBrief extends ProactiveOpportunity {
  brief: string; // the full instructions given to the agent for the call
}
