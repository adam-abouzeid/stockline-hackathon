/**
 * « Appel en cours » — a REAL phone call of the agent (PHONE_MODE=twilio), live, for the audience: who is called, the call's
 * state, what the client says and what the agent answers, each tool it runs, and the order changing as it happens.
 * Read-only: events come from the AI service (GET /ai/phone/live, Server-Sent Events); the order is re-read from the ERP after
 * each tool. A page opened in the middle of a call catches up (the service replays the call's events first).
 */
import { useEffect, useReducer, useRef } from "react";
import { Link } from "react-router-dom";
import { Check, PhoneCall, PhoneOff, Smartphone, Wrench, X } from "lucide-react";
import type { PhoneLiveEvent } from "@kit/shared";
import { AI_BASE } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useOrder } from "@/lib/queries";
import { Badge, Dot, SECTION_LABEL } from "@/ui";

type Line =
  | { kind: "caller"; text: string; final: boolean; ignored?: boolean }
  | { kind: "agent"; text: string; done: boolean }
  | { kind: "tool"; name: string; ok?: boolean; ms?: number }
  | { kind: "info"; text: string; tone?: "warning" | "destructive" | "muted" };

interface CallState {
  callId?: string;
  status?: string;
  clientName?: string;
  contactName?: string;
  title?: string;
  orderId?: string;
  to?: string;
  result?: string;
  note?: string;
  firstAudioMs?: number;
  lines: Line[];
  toolsDone: number;
}

const EMPTY: CallState = { lines: [], toolsDone: 0 };

function lastIndex<T>(items: T[], pred: (item: T) => boolean): number {
  for (let i = items.length - 1; i >= 0; i--) if (pred(items[i])) return i;
  return -1;
}

const TOOL_LABEL: Record<string, string> = {
  update_order: "change la date de livraison",
  update_order_line: "change une quantité",
  remove_order_line: "retire une ligne",
  add_order_line: "ajoute une ligne",
  confirm_order: "confirme la commande",
  cancel_order: "annule la commande",
  find_alternatives: "cherche un produit équivalent",
  record_call_outcome: "note la décision dans le dossier",
  get_order: "relit la commande",
  get_client: "relit la fiche client",
  get_product_stock: "vérifie le stock",
};

function reduce(state: CallState, ev: PhoneLiveEvent): CallState {
  const s: CallState = ev.callId !== state.callId ? { ...EMPTY, callId: ev.callId } : { ...state, lines: [...state.lines] };
  const last = s.lines[s.lines.length - 1];
  switch (ev.type) {
    case "call":
      s.status = ev.status;
      if (ev.clientName) Object.assign(s, { clientName: ev.clientName, contactName: ev.contactName, title: ev.title, orderId: ev.orderId, to: ev.to });
      if (ev.status === "ended") {
        s.result = ev.result;
        s.note = ev.note;
      }
      return s;
    case "transcript": {
      // the sentence being spoken is updated in place, even if an info line (barge-in) landed after its first words
      const open = lastIndex(s.lines, (l) => l.kind === "caller" && !l.final);
      const line: Line = { kind: "caller", text: ev.text, final: ev.final, ignored: ev.ignored };
      if (open >= 0) s.lines[open] = line;
      else if (!(ev.final && last?.kind === "caller" && last.final && last.text === ev.text)) s.lines.push(line);
      return s;
    }
    case "agent_text":
      if (last?.kind === "agent" && !last.done) s.lines[s.lines.length - 1] = { ...last, text: last.text + ev.delta };
      else s.lines.push({ kind: "agent", text: ev.delta.trimStart(), done: false });
      return s;
    case "agent_done": {
      const i = lastIndex(s.lines, (l) => l.kind === "agent" && !l.done);
      if (i >= 0) s.lines[i] = { ...(s.lines[i] as Extract<Line, { kind: "agent" }>), done: true };
      return s;
    }
    case "agent_tool":
      if (ev.ok === undefined) s.lines.push({ kind: "tool", name: ev.name });
      else {
        const i = lastIndex(s.lines, (l) => l.kind === "tool" && l.name === ev.name && l.ok === undefined);
        if (i >= 0) s.lines[i] = { kind: "tool", name: ev.name, ok: ev.ok, ms: ev.ms };
        s.toolsDone += 1;
      }
      // the agent's next words start a new bubble
      if (last?.kind === "agent" && !last.done) s.lines.splice(s.lines.lastIndexOf(last), 1, { ...last, done: true });
      return s;
    case "latency":
      s.firstAudioMs = ev.pickupToFirstAudioMs;
      return s;
    case "barge_in":
      s.lines.push({ kind: "info", text: "Le client parle : l'agent s'interrompt", tone: "muted" });
      return s;
    case "hangup":
      s.lines.push({ kind: "info", text: ev.note, tone: "muted" });
      return s;
    case "error":
      s.lines.push({ kind: "info", text: ev.message, tone: "destructive" });
      return s;
    default:
      return s;
  }
}

const STATUS_LABEL: Record<string, { label: string; tone: "warning" | "success" | "muted" | "violet" | "destructive"; pulse?: boolean }> = {
  dialling: { label: "Numérotation…", tone: "warning", pulse: true },
  ringing: { label: "Le téléphone sonne", tone: "warning", pulse: true },
  answered: { label: "En ligne", tone: "success", pulse: true },
  voicemail: { label: "Messagerie", tone: "muted" },
  ended: { label: "Terminé", tone: "muted" },
};
const RESULT_LABEL: Record<string, string> = { completed: "Appel terminé", missed: "Manqué", declined: "Refusé", cancelled: "Annulé" };

export function LiveCall() {
  const [call, dispatch] = useReducer(reduce, EMPTY);
  const order = useOrder(call.orderId);
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const source = new EventSource(`${AI_BASE}/phone/live`);
    source.onmessage = (m) => {
      try {
        dispatch(JSON.parse(m.data) as PhoneLiveEvent);
      } catch { /* keep-alive */ }
    };
    return () => source.close();
  }, []);
  // the order is re-read after each tool the agent ran (date, quantity, confirmation…)
  const { refetch } = order;
  useEffect(() => {
    // never cancel a fetch in flight (a page opened mid-call replays many tool events at once)
    if (call.orderId && call.toolsDone > 0) void refetch({ cancelRefetch: false });
  }, [call.toolsDone, call.orderId, refetch]);
  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [call.lines.length, call.lines[call.lines.length - 1]]);

  if (!call.callId) {
    return (
      <div className="flex items-center gap-2 rounded-[6px] border border-dashed border-border px-3.5 py-3 text-[12.5px] text-muted-foreground">
        <Smartphone size={14} strokeWidth={1.75} /> Aucun appel en cours. Dès que l'agent appelle, la conversation s'affiche ici en direct.
      </div>
    );
  }
  const st = STATUS_LABEL[call.status ?? "dialling"] ?? STATUS_LABEL.dialling;
  const ended = call.status === "ended";
  return (
    <div className={cn("grid gap-4 rounded-[6px] border p-3.5 lg:grid-cols-[minmax(0,1fr)_340px]", ended ? "border-border" : "border-violet/40")}>
      <div className="flex min-w-0 flex-col gap-2.5">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="flex items-center gap-2 text-[13px] font-medium">
            {ended ? <PhoneOff size={14} strokeWidth={1.75} /> : <PhoneCall size={14} strokeWidth={1.75} className="text-violet" />}
            {call.clientName ?? "Client"}
          </span>
          {call.contactName ? <span className="text-[12px] text-muted-foreground">{call.contactName}</span> : null}
          <span className="flex items-center gap-1.5 text-[12px]"><Dot tone={st.tone} pulse={st.pulse && !ended} /> {ended ? RESULT_LABEL[call.result ?? ""] ?? st.label : st.label}</span>
          {call.firstAudioMs !== undefined ? <Badge tone="violet">premiers mots {(call.firstAudioMs / 1000).toFixed(1)} s après le décroché</Badge> : null}
          {call.to ? <span className="ml-auto text-[11.5px] text-muted-foreground">téléphone de démo {call.to}</span> : null}
        </div>
        {call.title ? <p className="text-[12.5px] text-muted-foreground">{call.title}</p> : null}
        <div ref={scroller} className="flex max-h-[420px] min-h-[160px] flex-col gap-1.5 overflow-y-auto pr-1" aria-live="polite">
          {call.lines.length === 0 ? <p className="text-[12.5px] text-muted-foreground">L'agent prépare ses premiers mots pendant que le téléphone sonne…</p> : null}
          {call.lines.map((l, i) => <LineView key={`${i}-${l.kind}-${l.kind === "tool" ? l.name : l.kind === "caller" ? l.text.slice(0, 10) : ""}`} l={l} />)}
        </div>
        {ended && call.note && !call.lines.some((l) => l.kind === "info" && l.text === call.note) ? (
          <p className="text-[12px] text-muted-foreground">{call.note}</p>
        ) : null}
      </div>
      <div className="min-w-0 rounded-[6px] border border-border">
        <div className="flex h-9 items-center px-3"><span className={SECTION_LABEL}>La commande, en direct</span></div>
        <p className="px-3 pb-3 text-[12.5px] text-muted-foreground">
          {!call.orderId ? "Pas de commande liée à cet appel." : order.isError ? "Commande introuvable." : order.data ? "Chargement…" : "Chargement…"}
        </p>
        {order.data ? (
          <Link to={`/orders/${order.data.id}`} className="block px-3 pb-3 text-[12px] font-medium text-violet hover:underline">Ouvrir la commande</Link>
        ) : null}
      </div>
    </div>
  );
}

function LineView({ l }: { l: Line }) {
  switch (l.kind) {
    case "caller":
      return (
        <div className={cn("max-w-[85%] self-start rounded-[6px] bg-muted px-2.5 py-1.5 text-[13px]", (!l.final || l.ignored) && "text-muted-foreground")}>
          <span className="mr-1.5 text-[10.5px] uppercase tracking-[.08em] text-muted-foreground">Client</span>
          {l.text}
          {l.ignored ? <span className="ml-1.5 text-[11px]">(l'agent parlait : ignoré)</span> : null}
        </div>
      );
    case "agent":
      return (
        <div className="max-w-[85%] self-end rounded-[6px] border border-violet/30 bg-violet/[.06] px-2.5 py-1.5 text-[13px]">
          <span className="mr-1.5 text-[10.5px] uppercase tracking-[.08em] text-violet">Agent</span>
          {l.text}
        </div>
      );
    case "tool":
      return (
        <div className="flex items-center gap-1.5 self-end text-[11.5px] text-muted-foreground">
          <Wrench size={12} strokeWidth={1.75} />
          {TOOL_LABEL[l.name] ?? l.name}
          {l.ok === undefined ? <Dot tone="violet" pulse /> : l.ok ? <Check size={12} className="text-success" /> : <X size={12} className="text-destructive" />}
          {l.ms !== undefined ? <span className="num">{l.ms} ms</span> : null}
        </div>
      );
    case "info":
      return <div className={cn("self-center text-[11.5px]", l.tone === "destructive" ? "text-destructive" : "text-muted-foreground")}>{l.text}</div>;
  }
}
