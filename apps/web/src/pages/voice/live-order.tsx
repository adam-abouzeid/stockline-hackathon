/**
 * V2 — "Commande en cours": the order the voice agent is building, live, above the ERP feed.
 * Lines, total and delivery date update as the agent writes; the guards are visible (blocked client / credit limit →
 * "à valider par Martine", with a link to the order where a human can confirm). Read-only: it never acts on the order.
 */
import { Link } from "react-router-dom";
import { ArrowUpRight, ShieldAlert, ShoppingCart } from "lucide-react";
import { cn } from "@/lib/cn";
import { fmtDate, fmtMoney } from "@/lib/format";
import { useEvents, useOrder } from "@/lib/queries";
import { Badge, SECTION_LABEL, StatusDot } from "@/ui";

const BLOCKING = ["client_blocked", "credit_limit"];

export function LiveOrder() {
  const { data: events } = useEvents(200);
  // Events come newest first: the latest order the voice agent touched.
  const orderId = (events ?? []).find((e) => e.actor === "voice_agent" && e.entity === "order")?.entityId;
  const { data: order } = useOrder(orderId);

  return (
    <div className="shrink-0 border-b border-border">
      <div className="flex h-10 items-center gap-2 px-4">
        <ShoppingCart size={13} strokeWidth={1.75} className="text-violet" />
        <span className={SECTION_LABEL}>Commande en cours</span>
        {order ? <span className="num ml-auto text-[11.5px] text-muted-foreground">{order.number}</span> : null}
      </div>
      {!order ? (
        <p className="px-4 pb-4 text-[12.5px] text-muted-foreground">Aucune commande pour l'instant : elle apparaît ici dès que l'agent la crée.</p>
      ) : (
        <OrderBody order={order} />
      )}
    </div>
  );
}

function OrderBody({ order }: { order: NonNullable<ReturnType<typeof useOrder>["data"]> }) {
  const blocking = order.warnings.filter((w) => BLOCKING.includes(w.code));
  const needsHuman = order.status === "draft" && blocking.length > 0;
  const total = order.lines.reduce((s, l) => s + l.qty * l.unitPrice, 0);

  return (
    <div className="flex flex-col gap-2.5 px-4 pb-3.5">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[12.5px]">
        <span className="font-medium">{order.client.name}</span>
        <StatusDot kind="order" value={order.status} />
        {order.deliveryDate ? <span className="text-muted-foreground">livraison {fmtDate(order.deliveryDate)}</span> : null}
      </div>

      <ul className="flex flex-col divide-y divide-border rounded-[6px] border border-border">
        {order.lines.length === 0 ? (
          <li className="px-3 py-2 text-[12.5px] text-muted-foreground">Aucune ligne pour l'instant</li>
        ) : (
          order.lines.map((l) => (
            <li key={l.id} className="flex items-baseline gap-2 px-3 py-1.5 text-[12.5px]">
              <span className="num w-9 shrink-0 text-right font-medium">{l.qty}×</span>
              <span className="min-w-0 flex-1 truncate" title={l.productName}>{l.productName}</span>
              <span className="num shrink-0 text-muted-foreground">{fmtMoney(l.qty * l.unitPrice)}</span>
            </li>
          ))
        )}
        <li className="flex items-baseline justify-between px-3 py-1.5 text-[12.5px] font-medium">
          <span>Total HT</span>
          <span className="num">{fmtMoney(total)}</span>
        </li>
      </ul>

      {needsHuman ? (
        <div className="flex flex-col gap-1.5 rounded-[6px] border border-destructive/40 bg-destructive/[.06] px-3 py-2" role="alert">
          <span className="flex items-center gap-1.5 text-[12.5px] font-medium">
            <ShieldAlert size={14} strokeWidth={1.75} className="text-destructive" />
            Bloquée pour l'agent : à valider par la comptabilité (Martine)
          </span>
          <ul className="text-[12px] text-secondary-foreground">
            {blocking.map((w, i) => <li key={i}>{w.message}</li>)}
          </ul>
          <Link to={`/orders/${order.id}`} className="inline-flex items-center gap-1 text-[12px] font-medium text-violet hover:underline">
            Ouvrir la commande pour la valider <ArrowUpRight size={12} strokeWidth={1.75} />
          </Link>
        </div>
      ) : (
        <p className={cn("text-[12px]", order.status === "confirmed" ? "text-success" : "text-muted-foreground")}>
          {order.status === "draft" ? "Brouillon : l'agent attend l'accord clair du client avant de confirmer." : null}
          {order.status === "confirmed" ? "Confirmée avec l'accord du client." : null}
          {order.status === "cancelled" ? "Annulée." : null}
        </p>
      )}

      {order.warnings.length > blocking.length ? (
        <div className="flex flex-wrap gap-1">
          {order.warnings.filter((w) => !BLOCKING.includes(w.code)).map((w, i) => <Badge key={i} tone="warning">{w.message}</Badge>)}
        </div>
      ) : null}
    </div>
  );
}
