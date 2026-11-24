/**
 * V3 — the agent phones by itself. When it decides to call a client, the call RINGS here, on whatever page is open. In the product,
 * the agent dials the client's real phone; in the demo this window simulates the client's phone: picking up ("Décrocher") opens the
 * Voix page and the agent speaks first. The click is also the user gesture the browser needs to play the agent's first words.
 * Nobody presses "call" on the agent's behalf.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Phone, PhoneOff } from "lucide-react";
import { api } from "@/lib/api";
import { Badge, Button, Dot } from "@/ui";

export function IncomingCall() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["proactive", "ringing"],
    queryFn: () => api.proactive.calls("ringing"),
    refetchInterval: 3000,
    refetchIntervalInBackground: true,
  });
  const refresh = () => qc.invalidateQueries({ queryKey: ["proactive"] });
  const answer = useMutation({
    mutationFn: (id: string) => api.proactive.answer(id),
    onSuccess: (c) => {
      refresh();
      navigate(`/voice?outbound=${encodeURIComponent(c.opportunityId)}&autostart=1`);
    },
    onError: refresh, // someone else picked up, or it was missed: just refresh
  });
  const decline = useMutation({ mutationFn: (id: string) => api.proactive.decline(id), onSettled: refresh });

  const call = data?.[0];
  if (!call) return null;
  return (
    <div role="alertdialog" aria-label="Appel entrant de l'agent" className="fixed bottom-5 right-5 z-50 w-[360px] rounded-[8px] border border-violet/40 bg-card p-4 shadow-lg">
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-wide text-muted-foreground">
        <Dot tone="violet" pulse /> Simulateur : téléphone du client (démo)
      </div>
      <div className="mt-2 text-[14px] font-medium">L'agent appelle {call.clientName}</div>
      {call.contactName ? <div className="text-[12px] text-muted-foreground">{call.contactName}</div> : null}
      <p className="mt-2 text-[12.5px]">{call.title}</p>
      {call.deadline ? <Badge tone="warning" className="mt-2">{call.deadline}</Badge> : null}
      <div className="mt-3.5 flex gap-2">
        <Button size="sm" icon={Phone} disabled={answer.isPending} onClick={() => answer.mutate(call.id)}>Décrocher</Button>
        <Button size="sm" variant="ghost" icon={PhoneOff} disabled={decline.isPending} onClick={() => decline.mutate(call.id)}>Refuser</Button>
      </div>
    </div>
  );
}
