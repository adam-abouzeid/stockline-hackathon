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
  deadline: string;
  priority: number;
  status: CallStatus;
  createdAt: string;
  endedAt?: string;
  outcome?: string; // what was decided on the call (the line the agent wrote in the client's history)
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
