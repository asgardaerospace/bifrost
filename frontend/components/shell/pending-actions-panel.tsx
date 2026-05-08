"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { ProposedActionRead } from "@/types/api";

const STATUS_TONE: Record<string, string> = {
  pending: "text-amber",
  approved: "text-green",
  rejected: "text-red",
  executed: "text-green",
};

function ProposedActionRow({
  action,
  onDecide,
}: {
  action: ProposedActionRead;
  onDecide: (id: number, decision: "approved" | "rejected") => void;
}) {
  const tone = STATUS_TONE[action.status] ?? "text-mute2";
  const payload = action.payload ?? {};
  const rationale = typeof payload.rationale === "string" ? payload.rationale : null;
  const otherKeys = Object.keys(payload).filter(
    (k) => k !== "rationale" && k !== "_decision",
  );

  return (
    <li className="rounded-md border border-border/60 bg-panel2/40 p-3">
      <header className="flex items-center justify-between font-mono text-[10px] uppercase tracking-wider text-mute2">
        <div className="flex items-center gap-2">
          <span className="text-accent">{action.action_type}</span>
          {action.target_entity_type && (
            <span>
              · {action.target_entity_type}
              {action.target_entity_id !== null && action.target_entity_id !== undefined
                ? ` #${action.target_entity_id}`
                : ""}
            </span>
          )}
          {action.requires_approval && (
            <span className="chip text-amber">approval-gated</span>
          )}
        </div>
        <span className={tone}>{action.status}</span>
      </header>

      {rationale && (
        <p className="mt-2 text-xs text-ink leading-relaxed">{rationale}</p>
      )}

      {otherKeys.length > 0 && (
        <details className="mt-2">
          <summary className="cursor-pointer font-mono text-[10px] uppercase tracking-widest text-mute2 hover:text-accent">
            payload
          </summary>
          <pre className="mt-1 max-h-40 overflow-auto rounded-md bg-bgdeep/60 p-2 font-mono text-[10px] text-ink">
            {JSON.stringify(
              Object.fromEntries(otherKeys.map((k) => [k, payload[k]])),
              null,
              2,
            )}
          </pre>
        </details>
      )}

      <div className="mt-2 flex items-center justify-between gap-2 border-t border-border/60 pt-2 font-mono text-[10px] text-mute2">
        <span>run #{action.autonomy_operation_id} · staged {new Date(action.created_at).toLocaleString()}</span>
        {action.status === "pending" && (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => onDecide(action.id, "rejected")}
              className="rounded-md border border-red/40 px-3 py-1 uppercase tracking-widest text-red hover:bg-red/10"
            >
              reject
            </button>
            <button
              type="button"
              onClick={() => onDecide(action.id, "approved")}
              className="rounded-md border border-green/40 bg-green/10 px-3 py-1 uppercase tracking-widest text-green hover:bg-green/20"
            >
              approve
            </button>
          </div>
        )}
        {action.status !== "pending" && (
          <span>
            {action.status} ·{" "}
            {(action.payload as { _decision?: { by?: string } } | null)?._decision?.by ?? "—"}
          </span>
        )}
      </div>
    </li>
  );
}

export function PendingActionsPanel() {
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["proposed-actions", "pending"],
    queryFn: () => api.listProposedActions({ status: "pending", limit: 50 }),
    staleTime: 10_000,
    refetchInterval: 15_000,
  });

  const decide = useMutation({
    mutationFn: ({
      id,
      decision,
    }: {
      id: number;
      decision: "approved" | "rejected";
    }) =>
      api.decideProposedAction(id, {
        decision,
        decided_by: "operator",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["proposed-actions"] });
      qc.invalidateQueries({ queryKey: ["agent-runs"] });
    },
  });

  return (
    <section className="rounded-lg border border-border/60 bg-panel/60">
      <header className="flex items-center justify-between border-b border-border/60 px-4 py-3">
        <span className="font-mono text-2xs uppercase tracking-widest text-amber">
          ⚠ pending actions
        </span>
        <span className="font-mono text-2xs text-mute2">
          {data?.length ?? 0} awaiting decision
        </span>
      </header>
      {isLoading && (
        <div className="px-4 py-6 text-center font-mono text-2xs text-mute2 animate-soft-pulse">
          ▸ loading proposals…
        </div>
      )}
      {!isLoading && (data?.length ?? 0) === 0 && (
        <div className="px-4 py-6 text-center font-mono text-2xs text-mute2">
          no pending actions · agents have nothing to escalate
        </div>
      )}
      <ul className="flex flex-col gap-2 p-3">
        {(data ?? []).map((a) => (
          <ProposedActionRow
            key={a.id}
            action={a}
            onDecide={(id, decision) => decide.mutate({ id, decision })}
          />
        ))}
      </ul>
    </section>
  );
}
