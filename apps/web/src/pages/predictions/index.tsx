/**
 * Prévisions — what a seller should act on this week, in three lists:
 *  1. coming demand peaks (season radar) with the date to order by,
 *  2. stock that will not sell before it expires, with offers to propose (drafts: nothing is sent),
 *  3. the existing low-stock rule (the stockout engine of the team plugs in here).
 * Everything is read from /api/predictions/* and the dashboard; the only write is "offer proposed" (a client-history line).
 */
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { CalendarClock, PackageCheck, TrendingUp } from "lucide-react";
import type { RescueClient, RescueItem, SeasonPeak, SupplierBasket } from "@kit/shared";
import { api } from "@/lib/api";
import { businessToday } from "@/lib/clock";
import { fmtDate, fmtMoney } from "@/lib/format";
import { qk, useApiMutation, useDashboard } from "@/lib/queries";
import { Badge, Button, EmptyState, ErrorState, Page, PageBody, PageHeader, Section, Skeleton } from "@/ui";

const num = (v: number) => v.toLocaleString("fr-FR", { maximumFractionDigits: 1 });
const pct = (v?: number) => (v === undefined ? "—" : `${Math.round(v * 100)} %`);
const yearAgo = (iso: string) => {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() - 364);
  return d.toISOString().slice(0, 10);
};

export default function PredictionsPage() {
  return (
    <Page>
      <PageHeader title="Prévisions" icon={<TrendingUp size={15} strokeWidth={1.75} />} meta="Ce qu'il faut préparer cette semaine" />
      <PageBody>
        <div className="mx-auto flex max-w-[1080px] flex-col gap-8">
          <Radar />
          <Rescue />
          <LowStock />
        </div>
      </PageBody>
    </Page>
  );
}

// ───────── 1. Season radar ─────────

function Radar() {
  const radar = useQuery({ queryKey: ["predictions", "radar"], queryFn: () => api.predictions.seasonRadar() });
  const asOf = yearAgo(businessToday());
  const proof = useQuery({ queryKey: ["predictions", "backtest", asOf], queryFn: () => api.predictions.radarBacktest(asOf) });
  const d = radar.data;

  return (
    <Section title="Pics de demande à venir" count={d?.peaks.length}>
      <p className="mb-3 max-w-[760px] text-[12.5px] text-muted-foreground">
        Chaque produit a des semaines où il se vend au moins deux fois plus que d'habitude, et elles reviennent chaque année. Le radar les repère dans les
        trois ans de ventes et compte à rebours en tenant compte du délai du fournisseur. Les bons de commande en brouillon ne comptent jamais comme du stock attendu.
      </p>
      {radar.isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : radar.isError || !d ? (
        <ErrorState onRetry={() => radar.refetch()} />
      ) : d.peaks.length === 0 ? (
        <EmptyState compact icon={CalendarClock} title="Aucun pic annoncé dans les semaines à venir" />
      ) : (
        <>
          <div className="mb-3 flex flex-wrap gap-1.5">{d.suppliers.map((b) => <BasketChip key={b.supplierId} b={b} />)}</div>
          <ul className="flex flex-col divide-y divide-border rounded-[6px] border border-border">
            {d.peaks.map((p) => <PeakRow key={p.productId} p={p} />)}
          </ul>
        </>
      )}
      {proof.data ? (
        <p className="mt-3 max-w-[760px] text-[12px] text-muted-foreground">
          <b className="font-medium text-foreground">Vérification.</b> Le radar du {fmtDate(asOf)}, qui ne voyait que le passé, a annoncé {proof.data.announced} pics :{" "}
          {pct(proof.data.precision)} ont vraiment eu lieu dans la période annoncée, mais seulement {proof.data.exactWeekHits} sur {proof.data.announced} pendant la
          semaine exacte. Il a retrouvé {pct(proof.data.recall)} des vrais pics : il en rate. Utilisez-le pour savoir quoi surveiller, pas pour fixer le jour près.
        </p>
      ) : null}
    </Section>
  );
}

function BasketChip({ b }: { b: SupplierBasket }) {
  return (
    <Badge tone={b.meetsMinimum ? "success" : "warning"}>
      {b.supplierName} · {fmtMoney(b.totalCost)} · avant le {fmtDate(b.orderBy)}
      {b.minOrderAmount ? ` · minimum ${fmtMoney(b.minOrderAmount)} ${b.meetsMinimum ? "atteint" : "non atteint"}` : ""}
    </Badge>
  );
}

function PeakRow({ p }: { p: SeasonPeak }) {
  return (
    <li className="flex flex-wrap items-start gap-x-6 gap-y-2 px-3 py-2.5">
      <div className="min-w-[260px] flex-1">
        <Link to={`/products/${p.productId}`} className="text-[13px] font-medium hover:underline">{p.productName}</Link>
        <p className="mt-0.5 text-[12px] text-muted-foreground">{p.reason}</p>
      </div>
      <Fact label="Pic">×{num(p.peakIndex)} dès le {fmtDate(p.rampWeekStart)}</Fact>
      <Fact label="Commander avant">
        <span className={p.late ? "font-medium text-destructive" : undefined}>{fmtDate(p.orderBy)}</span>
        {p.late ? <Badge tone="destructive" className="ml-1.5">en retard</Badge> : null}
      </Fact>
      <Fact label="Stock (+ attendu)">{num(p.available)} {p.incoming ? `(+${num(p.incoming)})` : ""}</Fact>
      <Fact label="Quantité conseillée">
        {p.suggestedQty > 0 ? `${num(p.suggestedQty)} ${p.unit}${p.estimatedCost ? ` · ${fmtMoney(p.estimatedCost)}` : ""}` : "Stock suffisant"}
      </Fact>
    </li>
  );
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="w-[150px] shrink-0 text-[12.5px]">
      <div className="text-[11px] text-muted-foreground">{label}</div>
      <div className="num">{children}</div>
    </div>
  );
}

// ───────── 2. Stock to rescue ─────────

function Rescue() {
  const q = useQuery({ queryKey: ["predictions", "rescue"], queryFn: () => api.predictions.stockRescue() });
  return (
    <Section title="Stock à écouler avant la date limite" count={q.data?.items.length}>
      <p className="mb-3 max-w-[760px] text-[12.5px] text-muted-foreground">
        Lots que le rythme de vente actuel n'écoulera pas à temps. Pour chacun : les clients qui l'achètent déjà et une remise qui ne descend jamais sous le coût.
        Ce sont des brouillons : le bouton note l'offre dans l'historique du client, rien n'est envoyé ni modifié.
      </p>
      {q.isLoading ? (
        <Skeleton className="h-32 w-full" />
      ) : q.isError || !q.data ? (
        <ErrorState onRetry={() => q.refetch()} />
      ) : q.data.items.length === 0 ? (
        <EmptyState compact icon={PackageCheck} title="Rien à sauver" description="Tous les lots proches de leur date limite devraient se vendre à temps." />
      ) : (
        <div className="flex flex-col gap-3">{q.data.items.map((i) => <RescueCard key={i.productId} item={i} />)}</div>
      )}
    </Section>
  );
}

function RescueCard({ item: i }: { item: RescueItem }) {
  const propose = useApiMutation(api.predictions.proposeOffer, {
    success: "Offre notée dans l'historique du client",
    invalidate: [["predictions"], qk.clients.all],
  });
  const send = (c: RescueClient) =>
    propose.mutate({ clientId: c.clientId, productId: i.productId, qty: c.suggestedQty, discountPct: i.suggestedDiscountPct, offerPrice: c.offerPrice });

  return (
    <div className="rounded-[6px] border border-border p-3">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <Link to={`/products/${i.productId}`} className="text-[13px] font-medium hover:underline">{i.productName}</Link>
        <Badge tone={i.daysToExpiry <= 7 ? "destructive" : "warning"}>date limite dans {i.daysToExpiry} j</Badge>
        <span className="num text-[12px] text-muted-foreground">
          {num(i.atRiskUnits)} {i.unit} en danger ({fmtMoney(i.atRiskValue)} au coût) · {num(i.weeklySales)} vendus par semaine
        </span>
      </div>
      <p className="mt-1 text-[12px] text-muted-foreground">{i.reason}</p>
      {i.clients.length === 0 ? (
        <p className="mt-2 text-[12px]">Aucun client actif n'a acheté ce produit ces 90 derniers jours.</p>
      ) : (
        <ul className="mt-2 divide-y divide-border rounded-[6px] border border-border">
          {i.clients.map((c) => (
            <li key={c.clientId} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-3 py-1.5 text-[12.5px]">
              <Link to={`/clients/${c.clientId}`} className="min-w-[200px] flex-1 font-medium hover:underline">{c.clientName}</Link>
              <span className="num text-muted-foreground">{c.ordersLast90d} commandes en 90 j</span>
              <span className="num">{num(c.suggestedQty)} × {fmtMoney(c.offerPrice)} <s className="text-muted-foreground">{fmtMoney(c.unitPrice)}</s></span>
              {c.alreadyProposed ? (
                <Badge tone="success">Proposée</Badge>
              ) : (
                <Button size="sm" disabled={propose.isPending} onClick={() => send(c)}>
                  Marquer comme proposée
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ───────── 3. Current low-stock rule ─────────

function LowStock() {
  const { data } = useDashboard();
  const low = data?.lowStock ?? [];
  return (
    <Section title="Risque de rupture (règle actuelle)" count={low.length}>
      <p className="mb-3 max-w-[760px] text-[12.5px] text-muted-foreground">
        Règle du tableau de bord : le stock couvre moins de 2 jours de ventes (moyenne des 14 derniers jours). Elle ne tient compte ni des saisons ni du délai des fournisseurs :
        c'est ici que viendra la détection de rupture prévisionnelle.
      </p>
      {low.length === 0 ? (
        <p className="text-[12.5px] text-muted-foreground">Aucun produit sous 2 jours de couverture.</p>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {low.map((l) => (
            <Link key={l.productId} to={`/products/${l.productId}`}>
              <Badge tone={l.available <= 0 ? "destructive" : "warning"}>{l.name} · {num(l.available)} {l.unit}</Badge>
            </Link>
          ))}
        </div>
      )}
    </Section>
  );
}
