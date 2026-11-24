/**
 * Appels du jour — the clients the voice agent phones FIRST, and only to solve a problem on an order they already have
 * (a product that cannot be delivered, a delivery day without a route). It never phones to sell or to chase a usual order.
 * The agent decides by itself; this page shows what it is dealing with and what was decided:
 *  - its state (on / paused) and how it decides,
 *  - the clients to warn, each with the problem, the deadline and what the agent will do,
 *  - the calls already placed and their outcome.
 * "Vérifier maintenant" only runs one decision cycle right away instead of waiting for the next tick. Calls ring on whatever page is
 * open (see IncomingCall); orders still go through draft → recap → explicit "yes".
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { CheckCircle2, PackageX, Pause, PhoneOutgoing, Play, RefreshCw, Truck } from "lucide-react";
import type { CallStatus, IssueKind, ProactiveCall, ProactiveOpportunity } from "@kit/shared";
import { api } from "@/lib/api";
import { Badge, Button, Dot, EmptyState, ErrorState, Page, PageBody, PageHeader, Section, Skeleton } from "@/ui";

const KIND: Record<IssueKind, { label: string; icon: typeof PackageX; does: string }> = {
  stock: { label: "Stock", icon: PackageX, does: "Expliquer la rupture et trouver une solution avec lui : attendre, retirer la ligne ou un produit équivalent s'il est d'accord." },
  delivery: { label: "Livraison", icon: Truck, does: "Lui dire qu'aucune tournée ne passe ce jour-là et lui proposer une date possible." },
};
const STATUS: Record<CallStatus, { label: string; tone: "warning" | "success" | "muted" | "destructive" }> = {
  ringing: { label: "L'appel sonne", tone: "warning" },
  answered: { label: "Décroché", tone: "success" },
  declined: { label: "Refusé", tone: "muted" },
  missed: { label: "Manqué", tone: "destructive" },
};
const hhmm = (iso: string) => new Date(iso).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
const urgent = (deadline: string) => /aujourd'hui|demain/i.test(deadline);

export default function ProactivePage() {
  const qc = useQueryClient();
  const state = useQuery({ queryKey: ["proactive", "state"], queryFn: () => api.proactive.autodial(), refetchInterval: 5000 });
  const calls = useQuery({ queryKey: ["proactive", "calls"], queryFn: () => api.proactive.calls(), refetchInterval: 4000 });
  const queue = useQuery({ queryKey: ["proactive", "list"], queryFn: () => api.proactive.list(), refetchInterval: 15000 });
  const refresh = () => qc.invalidateQueries({ queryKey: ["proactive"] });
  const toggle = useMutation({ mutationFn: (enabled: boolean) => api.proactive.setAutodial(enabled), onSuccess: refresh });
  const cycle = useMutation({ mutationFn: () => api.proactive.dispatch(), onSuccess: refresh });
  const s = state.data;
  const callOf = (o: ProactiveOpportunity) => calls.data?.find((c) => c.opportunityId === o.id);

  return (
    <Page>
      <PageHeader title="Appels du jour" icon={<PhoneOutgoing size={15} strokeWidth={1.75} />} meta="Prévenir les clients d'un problème sur leur commande" />
      <PageBody>
        <div className="mx-auto flex max-w-[960px] flex-col gap-7">
          <div className="rounded-[6px] border border-border p-3.5">
            <div className="flex flex-wrap items-center gap-3">
              <span className="flex items-center gap-2 text-[13px] font-medium">
                <Dot tone={s?.enabled ? "success" : "muted"} pulse={!!s?.enabled} />
                {!s ? "…" : s.enabled ? "L'agent appelle seul dès qu'un client doit être prévenu" : "En pause : l'agent n'appelle personne"}
              </span>
              <span className="ml-auto flex gap-2">
                <Button size="sm" icon={RefreshCw} disabled={cycle.isPending} onClick={() => cycle.mutate()}>Vérifier maintenant</Button>
                <Button size="sm" icon={s?.enabled ? Pause : Play} disabled={!s || toggle.isPending} onClick={() => toggle.mutate(!s?.enabled)}>
                  {s?.enabled ? "Mettre en pause" : "Reprendre"}
                </Button>
              </span>
            </div>
            {cycle.data?.status === "nothing" ? (
              <p className="mt-2 text-[12px] text-muted-foreground">Aucun appel à lancer : un appel sonne déjà, ou tous les clients concernés ont été prévenus.</p>
            ) : null}
            <details className="mt-2 text-[12px] text-muted-foreground">
              <summary className="cursor-pointer">Comment l'agent décide</summary>
              <ul className="mt-1.5 list-disc space-y-0.5 pl-5">
                <li>Il n'appelle que pour <b className="font-medium text-foreground">résoudre un problème sur une commande en cours</b> : produit en rupture ou stock insuffisant, jour de livraison sans tournée. Jamais pour vendre ni relancer une commande habituelle.</li>
                <li>Plus la livraison est proche, plus l'appel est urgent. Les commandes à plus de 30 jours ne sont pas traitées.</li>
                {s ? <li>Un seul appel à la fois (manqué après {s.ringSeconds} s), {s.cooldownSeconds} s de pause entre deux appels, jamais le même client deux fois dans la journée.</li> : null}
                <li>Il ne cite que des faits vérifiés dans l'ERP, ne promet ni heure ni e-mail, et ne remplace un produit qu'avec l'accord du client. Toute modification est récapitulée.</li>
              </ul>
            </details>
          </div>

          <Section title="Clients à prévenir" count={queue.data?.length}>
            {queue.isLoading ? (
              <Skeleton className="h-32 w-full" />
            ) : queue.isError || !queue.data ? (
              <ErrorState onRetry={() => queue.refetch()} />
            ) : queue.data.length === 0 ? (
              <EmptyState compact icon={CheckCircle2} title="Aucun client à prévenir" description="Toutes les commandes en cours peuvent être livrées comme prévu." />
            ) : (
              <ul className="flex flex-col gap-3">{queue.data.map((o) => <Mission key={o.id} o={o} call={callOf(o)} />)}</ul>
            )}
          </Section>

          <Section title="Appels passés" count={calls.data?.length}>
            {calls.isLoading ? (
              <Skeleton className="h-16 w-full" />
            ) : !calls.data || calls.data.length === 0 ? (
              <p className="text-[12.5px] text-muted-foreground">Aucun appel pour l'instant. Il apparaîtra ici dès que l'agent appelle un client.</p>
            ) : (
              <ul className="divide-y divide-border rounded-[6px] border border-border">{calls.data.map((c) => <CallRow key={c.id} c={c} />)}</ul>
            )}
          </Section>
        </div>
      </PageBody>
    </Page>
  );
}

function Mission({ o, call }: { o: ProactiveOpportunity; call?: ProactiveCall }) {
  const st = call ? STATUS[call.status] : null;
  return (
    <li className="rounded-[6px] border border-border p-3.5">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <Badge tone={urgent(o.deadline) ? "destructive" : "warning"}>{o.deadline}</Badge>
        {st ? <Badge tone={st.tone}>{st.label}</Badge> : null}
        <Link to={`/clients/${o.clientId}`} className="ml-auto text-[13px] font-medium hover:underline">{o.clientName}</Link>
        {o.contactName ? <span className="text-[12px] text-muted-foreground">{o.contactName}</span> : null}
      </div>
      <h3 className="mt-2 text-[14px] font-medium">{o.title}</h3>
      <ul className="mt-2 flex flex-col gap-1.5">
        {o.kinds.map((k) => {
          const Icon = KIND[k].icon;
          return (
            <li key={k} className="flex items-start gap-2 text-[12.5px]">
              <Icon size={14} strokeWidth={1.75} className="mt-0.5 shrink-0 text-muted-foreground" />
              <span><b className="font-medium">{KIND[k].label} : </b><span className="text-muted-foreground">{KIND[k].does}</span></span>
            </li>
          );
        })}
      </ul>
      <details className="mt-2 text-[12px] text-muted-foreground">
        <summary className="cursor-pointer">Faits vérifiés que l'agent peut citer</summary>
        <ul className="mt-1 list-disc pl-5">{o.facts.map((f, i) => <li key={i}>{f}</li>)}</ul>
      </details>
    </li>
  );
}

function CallRow({ c }: { c: ProactiveCall }) {
  const st = STATUS[c.status];
  return (
    <li className="flex flex-wrap items-start gap-x-4 gap-y-1 px-3.5 py-2.5 text-[12.5px]">
      <span className="num w-[44px] shrink-0 text-muted-foreground">{hhmm(c.createdAt)}</span>
      <div className="min-w-[240px] flex-1">
        <Link to={`/clients/${c.clientId}`} className="font-medium hover:underline">{c.clientName}</Link>
        <p className="text-muted-foreground">{c.title}</p>
        {c.outcome ? <p className="mt-0.5">Décision : {c.outcome}</p> : c.status === "answered" ? <p className="mt-0.5 text-muted-foreground">Appel en cours ou résultat pas encore noté.</p> : null}
      </div>
      <Badge tone={st.tone}>{st.label}</Badge>
    </li>
  );
}
