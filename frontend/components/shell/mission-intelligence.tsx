"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { MissionSignalRead } from "@/types/api";

const SIGNAL_TONE: Record<string, string> = {
  funding: "text-cyan",
  procurement: "text-accent",
  supplier_risk: "text-red",
  manufacturing: "text-amber",
  launch: "text-blue",
  geopolitical: "text-amber",
  regulatory: "text-amber",
  defense: "text-accent",
  partnership: "text-teal",
  acquisition: "text-cyan",
  market_shift: "text-mute2",
};

const SEVERITY_TONE: Record<string, string> = {
  info: "text-mute2",
  notice: "text-cyan",
  warning: "text-amber",
  critical: "text-red",
};

const IMPACT_TONE: Record<string, string> = {
  raises_pressure: "text-red",
  lowers_pressure: "text-green",
  opportunity: "text-green",
  escalation: "text-red",
  informational: "text-mute2",
};

function relTime(iso?: string | null) {
  if (!iso) return "—";
  const d = new Date(iso);
  const diff = Date.now() - d.getTime();
  const m = Math.round(diff / 60_000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h`;
  return `${Math.round(h / 24)}d`;
}

function SignalRow({ row }: { row: MissionSignalRead }) {
  const sig = row.signal;
  const rel = row.relevance;
  return (
    <li className="rounded-md border border-border/60 bg-panel2/40 p-3 hover:border-accent/40">
      <div className="flex items-center justify-between font-mono text-2xs uppercase tracking-wider text-mute2">
        <div className="flex items-center gap-2">
          <span className={SIGNAL_TONE[sig.signal_type] ?? "text-mute2"}>
            {sig.signal_type.replace("_", " ")}
          </span>
          <span className={SEVERITY_TONE[sig.severity] ?? "text-mute2"}>
            ● {sig.severity}
          </span>
          {sig.region && <span>{sig.region}</span>}
        </div>
        <span>{relTime(sig.published_at)}</span>
      </div>
      <div className="mt-1 text-sm text-ink">{sig.title}</div>
      {sig.summary && (
        <div className="mt-1 line-clamp-2 text-xs text-mute2">{sig.summary}</div>
      )}
      <div className="mt-2 flex items-center justify-between border-t border-border/60 pt-2 font-mono text-2xs uppercase tracking-wider text-mute2">
        <div className="flex items-center gap-3">
          <span title="decayed relevance score">
            relevance {rel.decayed_score}
          </span>
          {row.impact_type && (
            <span className={IMPACT_TONE[row.impact_type] ?? "text-mute2"}>
              {row.impact_type.replace("_", " ")} {row.contribution! >= 0 ? "+" : ""}
              {row.contribution}
            </span>
          )}
        </div>
        <span>{sig.source}</span>
      </div>
    </li>
  );
}

/**
 * Mission-scoped intelligence panel (Sprint 4).
 *
 * Doctrine: intelligence is operational infrastructure. The panel suppresses
 * everything below the relevance threshold (handled server-side) and shows
 * only the signals materially affecting this mission, with explainable
 * relevance + impact contribution.
 */
export function MissionIntelligence({ missionId }: { missionId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ["mission", missionId, "intelligence"],
    queryFn: () => api.missionIntelligence(missionId, 15),
    staleTime: 30_000,
  });

  return (
    <section className="rounded-lg border border-border/60 bg-panel/60">
      <header className="flex items-center justify-between border-b border-border/60 px-4 py-3">
        <span className="font-mono text-2xs uppercase tracking-widest text-accent/80">
          ▸ relevant intelligence
        </span>
        <span className="font-mono text-2xs text-mute2">
          {data?.count ?? 0} signals · suppressed below threshold
        </span>
      </header>

      {isLoading && (
        <div className="px-4 py-6 text-center font-mono text-2xs text-mute2 animate-soft-pulse">
          ▸ scoring against active intelligence…
        </div>
      )}

      {!isLoading && (data?.count ?? 0) === 0 && (
        <div className="px-4 py-8 text-center font-mono text-2xs text-mute2">
          ▸ no signals cleared the relevance threshold for this mission
        </div>
      )}

      <ul className="divide-y divide-border/60">
        {(data?.items ?? []).map((row) => (
          <SignalRow key={row.signal.id} row={row} />
        ))}
      </ul>
    </section>
  );
}
