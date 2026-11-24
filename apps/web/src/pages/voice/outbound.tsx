/**
 * Outbound call banner (V3): when the Voix page is opened with ?outbound=<opportunity>, shows who the agent is about to phone and
 * why, with a "Lancer l'appel" button. The press is also the user gesture that lets the browser play the agent's first words.
 */
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { PhoneOutgoing } from "lucide-react";
import { api } from "@/lib/api";
import { Badge, Button, Skeleton } from "@/ui";

export function OutboundBanner({ ready, started, onCall }: { ready: boolean; started: boolean; onCall: (id: string) => void }) {
  const [params] = useSearchParams();
  const id = params.get("outbound");
  const autostart = params.get("autostart") === "1"; // set when the client picked up an incoming call of the agent
  const [launched, setLaunched] = useState(false);
  const q = useQuery({ queryKey: ["proactive", "one", id], queryFn: () => api.proactive.get(id!), enabled: !!id });
  useEffect(() => {
    if (autostart && id && ready && !started && !launched && q.data) {
      setLaunched(true);
      onCall(id);
    }
  }, [autostart, id, ready, started, launched, q.data, onCall]);
  if (!id) return null;
  const o = q.data;
  return (
    <div className="flex shrink-0 flex-wrap items-center gap-x-4 gap-y-2 border-b border-border bg-violet/[.06] px-5 py-2.5">
      <PhoneOutgoing size={15} strokeWidth={1.75} className="shrink-0 text-violet" />
      {q.isLoading ? (
        <Skeleton className="h-4 w-72" />
      ) : !o ? (
        <span className="text-[12.5px]">Occasion d'appel introuvable (elle a peut-être changé).</span>
      ) : (
        <div className="min-w-[260px] flex-1">
          <div className="flex flex-wrap items-center gap-2 text-[13px]">
            <b className="font-medium">Appel sortant : {o.clientName}</b>
            {o.contactName ? <span className="text-muted-foreground">{o.contactName}</span> : null}
            {started ? <Badge tone="violet">en cours</Badge> : null}
          </div>
          <p className="text-[12.5px]">{o.title}</p>
          <p className="text-[12px] text-muted-foreground">{o.deadline}</p>
        </div>
      )}
      {o && !started && !launched ? (
        <Button size="sm" icon={PhoneOutgoing} disabled={!ready} onClick={() => onCall(id)}>
          Lancer l'appel
        </Button>
      ) : null}
    </div>
  );
}
