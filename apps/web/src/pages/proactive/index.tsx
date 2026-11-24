/**
 * Appels du jour — the agent decides BY ITSELF whom to phone. This page shows what it is doing:
 *  - its autonomy (on / paused) and the rules it follows,
 *  - the journal of the calls it placed (ringing, picked up, declined, missed),
 *  - the queue of occasions it found (read-only: nobody presses "call" for it).
 * "Lancer un cycle maintenant" only runs one decision cycle right away instead of waiting for the next tick.
 * Calls ring on whatever page is open (see IncomingCall); orders still go through draft → recap → explicit "yes".
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { PackageX, PhoneOutgoing, Play, Pause, Snowflake, Zap } from "lucide-react";
import type { CallStatus, OpportunityType, ProactiveCall, ProactiveOpportunity } from "@kit/shared";
import { api } from "@/lib/api";
import { Badge, Button, Dot, EmptyState, ErrorState, Page, PageBody, PageHeader, Section, Skeleton } from "@/ui";

const KIND: Record<OpportunityType, { label: string; tone: "destructive" | "warning" | "violet" | "muted" }> = {
  shortage_order: { label: "Rupture sur sa commande", tone: "destructive" },
  shortage_heads_up: { label: "Rupture à signaler", tone: "warning" },
  overdue: { label: "Commande en retard", tone: "violet" },
  seasonal: { label: "Saison à anticiper", tone: "muted" },
};
const STATUS: Record<CallStatus, { label: string; tone: "warning" | "success" | "muted" | "destructive" }> = {
  ringing: { label: "sonne", tone: "warning" },
  answered: { label: "décroché", tone: "success" },
  declined: { label: "refusé", tone: "muted" },
  missed: { label: "manqué", tone: "destructive" },
};
const hhmm = (iso: string) => new Date(iso).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

export default function ProactivePage() {
  const qc = useQueryClient();
  const state = useQuery({ queryKey: ["proactive", "state"], queryFn: () => api.proactive.autodial(), refetchInterval: 5000 });
  const calls = useQuery({ queryKey: ["proactive", "calls"], queryFn: () => api.proactive.calls(), refetchInterval: 4000 });
  const queue = useQuery({ queryKey: ["proactive", "list"], queryFn: () => api.proactive.list(), refetchInterval: 15000 });
  const refresh = () => qc.invalidateQueries({ queryKey: ["proactive"] });
  const toggle = useMutation({ mutationFn: (enabled: boolean) => api.proactive.setAutodial(enabled), onSuccess: refresh });
  const cycle = useMutation({ mutationFn: () => api.proactive.dispatch(), onSuccess: refresh });
  const s = state.data;

  return (
    <Page>
      <PageHeader title="Appels du jour" icon={<PhoneOutgoing size={15} strokeWidth={1.75} />} meta="L'agent appelle de lui-même" />
      <PageBody>
        <div className="mx-auto flex max-w-[1080px] flex-col gap-8">
          <Section title="Autonomie de l'agent">
            <div className="flex flex-wrap items-center gap-3">
              <span className="flex items-center gap-2 text-[13px]">
                <Dot tone={s?.enabled ? "success" : "muted"} pulse={!!s?.enabled} />
                {s ? (s.enabled ? "L'agent cherche seul qui appeler" : "En pause : l'agent n'appelle personne") : "…"}
              </span>
              <Button size="sm" icon={s?.enabled ? Pause : Play} disabled={!s || toggle.isPending} onClick={() => toggle.mutate(!s?.enabled)}>
                {s?.enabled ? "Mettre en pause" : "Reprendre"}
              </Button>
              <Button size="sm" icon={Zap} disabled={cycle.isPending} onClick={() => cycle.mutate()}>Lancer un cycle maintenant</Button>
              {cycle.data && cycle.data.status === "nothing" ? <span className="text-[12px] text-muted-foreground">Rien à appeler pour l'instant (un appel sonne déjà, ou tout est déjà traité).</span> : null}
            </div>
            {s ? (
              <p className="mt-2 max-w-[760px] text-[12px] text-muted-foreground">
                Règles : il regarde toutes les {s.intervalSeconds} s, fait sonner un seul appel à la fois (manqué après {s.ringSeconds} s), attend {s.cooldownSeconds} s entre deux appels,
                n'appelle jamais sous l'urgence {s.minPriority}, jamais deux fois le même client dans la journée, et ne réessaie pas une occasion déjà tentée pendant 30 minutes.
                Il ne cite que des faits vérifiés, ne promet ni heure ni e-mail, et toute commande passe par un récapitulatif et un « oui » clair.
              </p>
            ) : null}
          </Section>

          <Section title="Journal des appels de l'agent" count={calls.data?.length}>
            {calls.isLoading ? (
              <Skeleton className="h-20 w-full" />
            ) : !calls.data || calls.data.length === 0 ? (
              <EmptyState compact icon={Snowflake} title="Aucun appel pour l'instant" description="Il apparaîtra ici dès que l'agent décide d'appeler." />
            ) : (
              <ul className="divide-y divide-border rounded-[6px] border border-border">{calls.data.map((c) => <CallRow key={c.id} c={c} />)}</ul>
            )}
          </Section>

          <Section title="File d'attente : ce que l'agent va appeler" count={queue.data?.length}>
            {queue.isLoading ? (
              <Skeleton className="h-40 w-full" />
            ) : queue.isError || !queue.data ? (
              <ErrorState onRetry={() => queue.refetch()} />
            ) : (
              <ul className="flex flex-col gap-3">{queue.data.map((o) => <Occasion key={o.id} o={o} />)}</ul>
            )}
          </Section>
        </div>
      </PageBody>
    </Page>
  );
}

function CallRow({ c }: { c: ProactiveCall }) {
  const st = STATUS[c.status];
  return (
    <li className="flex flex-wrap items-center gap-x-4 gap-y-1 px-3 py-2 text-[12.5px]">
      <span className="num w-[70px] text-muted-foreground">{hhmm(c.createdAt)}</span>
      <Link to={`/clients/${c.clientId}`} className="min-w-[180px] font-medium hover:underline">{c.clientName}</Link>
      <span className="min-w-[200px] flex-1 text-muted-foreground">{c.title}</span>
      <Badge tone={st.tone}>{st.label}</Badge>
    </li>
  );
}

function Occasion({ o }: { o: ProactiveOpportunity }) {
  const kind = KIND[o.type];
  return (
    <li className="rounded-[6px] border border-border p-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <Badge tone={kind.tone}>{kind.label}</Badge>
        <Link to={`/clients/${o.clientId}`} className="text-[13px] font-medium hover:underline">{o.clientName}</Link>
        {o.contactName ? <span className="text-[12px] text-muted-foreground">{o.contactName}</span> : null}
        <span className="num ml-auto text-[11.5px] text-muted-foreground">urgence {o.priority}</span>
      </div>
      <p className="mt-1.5 text-[12.5px]">{o.reason}</p>
      <details className="mt-1.5 text-[12px] text-muted-foreground">
        <summary className="cursor-pointer">Faits vérifiés et objectif</summary>
        <ul className="mt-1 list-disc pl-5">{o.facts.map((f, i) => <li key={i}>{f}</li>)}</ul>
        <p className="mt-1"><b className="font-medium text-foreground">Objectif :</b> {o.objective}</p>
      </details>
      {o.type === "shortage_order" ? (
        <p className="mt-1 flex items-center gap-1 text-[11.5px] text-muted-foreground"><PackageX size={12} strokeWidth={1.75} /> À prévenir avant le départ du camion.</p>
      ) : null}
    </li>
  );
}
