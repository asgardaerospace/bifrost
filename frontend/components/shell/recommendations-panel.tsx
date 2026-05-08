"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { RecommendationRead } from "@/types/api";

const TYPE_TONE: Record<string, string> = {
  mitigate_supplier_risk: "text-red",
  escalate: "text-amber",
  executive_attention: "text-accent",
  route_approval: "text-amber",
  queue_reprioritize: "text-cyan",
  operational_followup: "text-blue",
  escalate_intelligence: "text-amber",
  coordinate_mission: "text-mute2",
};

const IMPACT_TONE: Record<string, string> = {
  raises_pressure: "text-red",
  lowers_pressure: "text-green",
  unblocks: "text-green",
  informational: "text-mute2",
};

function RecommendationRow({
  rec,
  onDecide,
}: {
  rec: RecommendationRead;
  onDecide: (id: number, decision: "accepted" | "dismissed") => void;
}) {
  return (
    <li className="rounded-md border border-border/60 bg-panel2/40 p-3">
      <div className="flex items-center justify-between font-mono text-2xs uppercase tracking-wider text-mute2">
        <div className="flex items-center gap-2">
          <span className={TYPE_TONE[rec.recommendation_type] ?? "text-mute2"}>
            {rec.recommendation_type.replace("_", " ")}
          </span>
          <span title="confidence">conf {rec.confidence}</span>
          {rec.projected_impact && (
            <span className={IMPACT_TONE[rec.projected_impact] ?? "text-mute2"}>
              {rec.projected_impact.replace("_", " ")}
              {rec.projected_delta !== null && rec.projected_delta !== undefined
                ? ` ${rec.projected_delta >= 0 ? "+" : ""}${rec.projected_delta}`
                : ""}
            </span>
          )}
        </div>
        <span>{rec.status}</span>
      </div>
      <div className="mt-1 text-sm text-ink">{rec.title}</div>
      <div className="mt-1 line-clamp-3 text-xs text-mute2">{rec.rationale}</div>
      {rec.citations && rec.citations.length > 0 && (
        <div className="mt-2 border-t border-border/60 pt-2">
          <div className="mb-1 font-mono text-[10px] uppercase tracking-widest text-mute2">
            sources
          </div>
          <ul className="flex flex-wrap gap-1">
            {rec.citations.slice(0, 4).map((c, i) => (
              <li
                key={i}
                className="rounded-md border border-border/60 bg-panel2/40 px-2 py-0.5 font-mono text-[10px] text-mute2"
                title={String(c.excerpt ?? "")}
              >
                {String(c.source_type)}#{String(c.source_id)}
              </li>
            ))}
          </ul>
        </div>
      )}
      {rec.status === "pending" && (
        <div className="mt-2 flex items-center justify-end gap-2 border-t border-border/60 pt-2">
          <button
            type="button"
            onClick={() => onDecide(rec.id, "dismissed")}
            className="rounded-md border border-border px-3 py-1 font-mono text-[10px] uppercase tracking-widest text-mute2 hover:border-red/40 hover:text-red"
          >
            dismiss
          </button>
          <button
            type="button"
            onClick={() => onDecide(rec.id, "accepted")}
            className="rounded-md border border-green/40 bg-green/10 px-3 py-1 font-mono text-[10px] uppercase tracking-widest text-green hover:bg-green/20"
          >
            accept
          </button>
        </div>
      )}
      {rec.status !== "pending" && rec.decided_by && (
        <div className="mt-2 border-t border-border/60 pt-2 font-mono text-[10px] uppercase tracking-widest text-mute2">
          {rec.status} by {rec.decided_by}
          {rec.decision_note ? ` — ${rec.decision_note}` : ""}
        </div>
      )}
    </li>
  );
}

export function RecommendationsPanel({ missionId }: { missionId?: number }) {
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["recommendations", missionId ?? "all"],
    queryFn: () =>
      missionId !== undefined
        ? api.missionRecommendations(missionId)
        : api.listRecommendations({ status: "pending", limit: 25 }),
    staleTime: 30_000,
  });

  const regenerate = useMutation({
    mutationFn: () => api.regenerateRecommendations(),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["recommendations"] }),
  });

  const decide = useMutation({
    mutationFn: ({
      id,
      decision,
    }: {
      id: number;
      decision: "accepted" | "dismissed";
    }) =>
      api.decideRecommendation(id, {
        decision,
        decided_by: "operator",
      }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["recommendations"] }),
  });

  return (
    <section className="rounded-lg border border-border/60 bg-panel/60">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 px-4 py-3">
        <span className="font-mono text-2xs uppercase tracking-widest text-accent/80">
          ▸ recommendations
        </span>
        <div className="flex items-center gap-3">
          <span className="font-mono text-2xs text-mute2">
            {data?.length ?? 0} grounded
          </span>
          <button
            type="button"
            onClick={() => regenerate.mutate()}
            disabled={regenerate.isPending}
            className="chip-accent rounded-md px-3 py-1 font-mono text-[10px] uppercase tracking-widest hover:bg-accent/30 disabled:opacity-50"
          >
            {regenerate.isPending ? "…" : "regenerate"}
          </button>
        </div>
      </header>
      {isLoading && (
        <div className="px-4 py-6 text-center font-mono text-2xs text-mute2 animate-soft-pulse">
          ▸ loading recommendations…
        </div>
      )}
      {!isLoading && (data?.length ?? 0) === 0 && (
        <div className="px-4 py-6 text-center font-mono text-2xs text-mute2">
          no pending recommendations · regenerate to scan operational state
        </div>
      )}
      <ul className="divide-y divide-border/60">
        {(data ?? []).map((r) => (
          <RecommendationRow
            key={r.id}
            rec={r}
            onDecide={(id, decision) => decide.mutate({ id, decision })}
          />
        ))}
      </ul>
    </section>
  );
}
