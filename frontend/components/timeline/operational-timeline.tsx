"use client";

/**
 * Unified operational timeline — Sprint 7.
 *
 * Replayable temporal layer across the entire operational habitat.
 * Operators can scrub the time window, filter by kind, and inspect
 * causal chains via cluster IDs.
 */

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { api } from "@/lib/api";
import { Empty, Panel, Pill } from "@/components/ui";
import type {
  OperationalTimelineEntry,
  OperationalTimelineKind,
} from "@/types/api";

const KIND_LABEL: Record<OperationalTimelineKind, string> = {
  operational_event: "event",
  approval_decided: "approval",
  proposed_action: "proposal",
  agent_run: "agent",
  recommendation: "recommendation",
  escalation: "escalation",
  pressure_shift: "pressure",
  workflow_stage: "workflow",
};

const SEVERITY_TONE: Record<string, "default" | "warn" | "danger" | "ok" | "accent"> = {
  info: "default",
  notice: "accent",
  warn: "warn",
  critical: "danger",
};

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}

function formatRelative(iso: string): string {
  try {
    const t = new Date(iso).getTime();
    const diff = Date.now() - t;
    const m = Math.round(diff / 60000);
    if (m < 1) return "now";
    if (m < 60) return `${m}m`;
    const h = Math.round(m / 60);
    if (h < 48) return `${h}h`;
    return `${Math.round(h / 24)}d`;
  } catch {
    return "";
  }
}

function EntryRow({
  entry,
  onCluster,
}: {
  entry: OperationalTimelineEntry;
  onCluster: (id: string) => void;
}) {
  return (
    <div className="grid grid-cols-[88px_120px_1fr] items-start gap-3 border-b border-border/60 py-2">
      <div className="font-mono text-2xs text-muted tabular-nums">
        <div>{formatTime(entry.occurred_at)}</div>
        <div className="text-[10px] text-muted/70">{formatRelative(entry.occurred_at)} ago</div>
      </div>
      <div className="flex flex-col gap-1">
        <Pill tone={SEVERITY_TONE[entry.severity] ?? "default"}>
          {entry.severity}
        </Pill>
        <span className="font-mono text-2xs uppercase tracking-wider text-muted">
          {KIND_LABEL[entry.kind] ?? entry.kind}
        </span>
        {entry.mission_codename && (
          <span className="font-mono text-2xs uppercase tracking-wider text-accent/80">
            {entry.mission_codename}
          </span>
        )}
      </div>
      <div className="min-w-0">
        <div className="truncate text-sm">{entry.title}</div>
        {entry.summary && (
          <div className="mt-0.5 line-clamp-2 text-xs text-muted">{entry.summary}</div>
        )}
        <div className="mt-1 flex flex-wrap items-center gap-2 font-mono text-[10px] text-muted">
          {entry.actor && <span>actor: {entry.actor}</span>}
          {entry.entity_type && (
            <span>
              {entry.entity_type}#{entry.entity_id}
            </span>
          )}
          {entry.cluster_id && (
            <button
              type="button"
              onClick={() => onCluster(entry.cluster_id!)}
              className="text-accent hover:underline"
            >
              cluster
            </button>
          )}
          {entry.causal_parent_id && (
            <span className="text-accent/70">caused by {entry.causal_parent_id}</span>
          )}
        </div>
      </div>
    </div>
  );
}

const KIND_OPTIONS: Array<{ value: OperationalTimelineKind | "all"; label: string }> = [
  { value: "all", label: "all" },
  { value: "operational_event", label: "events" },
  { value: "approval_decided", label: "approvals" },
  { value: "proposed_action", label: "proposals" },
  { value: "agent_run", label: "agents" },
  { value: "pressure_shift", label: "pressure" },
];

export function OperationalTimelineView({ missionId }: { missionId?: number }) {
  const [hours, setHours] = useState<number>(missionId ? 72 : 24);
  const [kindFilter, setKindFilter] = useState<OperationalTimelineKind | "all">("all");
  const [severityFilter, setSeverityFilter] = useState<"all" | "warn" | "critical">("all");
  const [clusterFilter, setClusterFilter] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["sprint7-timeline", missionId ?? "org", hours],
    queryFn: () =>
      missionId
        ? api.missionOperationalTimeline(missionId, { hours })
        : api.operationalTimeline({ hours }),
    refetchInterval: 30_000,
  });

  const entries = useMemo(() => {
    if (!data) return [];
    return data.entries.filter((e) => {
      if (kindFilter !== "all" && e.kind !== kindFilter) return false;
      if (severityFilter === "warn" && !["warn", "critical"].includes(e.severity)) return false;
      if (severityFilter === "critical" && e.severity !== "critical") return false;
      if (clusterFilter && e.cluster_id !== clusterFilter) return false;
      return true;
    });
  }, [data, kindFilter, severityFilter, clusterFilter]);

  return (
    <div className="space-y-4 p-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="font-mono text-2xs uppercase tracking-[0.3em] text-accent/70">
            operational timeline
          </div>
          <h1 className="mt-1 text-xl font-semibold text-inkhi">
            {missionId ? `Mission #${missionId} replay` : "Replayable operational evolution"}
          </h1>
          <p className="mt-1 text-xs text-muted">
            Unified temporal stream — events, approvals, agent runs, pressure
            shifts. Click a cluster to inspect a causal chain.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 font-mono text-2xs uppercase tracking-wider">
          {[6, 24, 72, 168].map((h) => (
            <button
              key={h}
              type="button"
              onClick={() => setHours(h)}
              className={
                "rounded border px-2 py-1 " +
                (h === hours
                  ? "border-accent/60 bg-accent/15 text-accent"
                  : "border-border bg-panel hover:bg-panel2")
              }
            >
              {h}h
            </button>
          ))}
        </div>
      </header>

      {error && (
        <Panel title="error">
          <Empty>Timeline unavailable.</Empty>
        </Panel>
      )}
      {isLoading && (
        <Panel title="loading">
          <Empty>Replaying operational evolution…</Empty>
        </Panel>
      )}

      {data && (
        <>
          <Panel title="filters">
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex flex-wrap gap-1 font-mono text-2xs uppercase tracking-wider">
                {KIND_OPTIONS.map((o) => (
                  <button
                    key={o.value}
                    type="button"
                    onClick={() => setKindFilter(o.value as OperationalTimelineKind | "all")}
                    className={
                      "rounded border px-2 py-1 " +
                      (o.value === kindFilter
                        ? "border-accent/60 bg-accent/15 text-accent"
                        : "border-border bg-panel hover:bg-panel2")
                    }
                  >
                    {o.label}
                    {o.value !== "all" && data.counts_by_kind[o.value]
                      ? ` (${data.counts_by_kind[o.value]})`
                      : ""}
                  </button>
                ))}
              </div>
              <div className="flex flex-wrap gap-1 font-mono text-2xs uppercase tracking-wider">
                {(["all", "warn", "critical"] as const).map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setSeverityFilter(s)}
                    className={
                      "rounded border px-2 py-1 " +
                      (s === severityFilter
                        ? "border-accent/60 bg-accent/15 text-accent"
                        : "border-border bg-panel hover:bg-panel2")
                    }
                  >
                    {s === "all" ? "any severity" : s}
                  </button>
                ))}
              </div>
              {clusterFilter && (
                <button
                  type="button"
                  onClick={() => setClusterFilter(null)}
                  className="rounded border border-accent/60 bg-accent/15 px-2 py-1 font-mono text-2xs uppercase tracking-wider text-accent"
                >
                  cluster · clear
                </button>
              )}
            </div>
          </Panel>

          {data.clusters.length > 0 && (
            <Panel title={`clusters · ${data.clusters.length}`}>
              <div className="flex flex-wrap gap-2">
                {data.clusters.map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() =>
                      setClusterFilter(clusterFilter === c.id ? null : c.id)
                    }
                    className={
                      "rounded-md border px-2 py-1 font-mono text-2xs uppercase tracking-wider transition-colors " +
                      (clusterFilter === c.id
                        ? "border-accent/60 bg-accent/15 text-accent"
                        : "border-border bg-panel hover:bg-panel2")
                    }
                    title={c.summary ?? undefined}
                  >
                    {c.label} · {c.entry_count}
                  </button>
                ))}
              </div>
            </Panel>
          )}

          <Panel title={`entries · ${entries.length} of ${data.count}`}>
            {entries.length === 0 ? (
              <Empty>No entries in window.</Empty>
            ) : (
              <div className="flex flex-col">
                {entries.map((e) => (
                  <EntryRow key={e.id} entry={e} onCluster={setClusterFilter} />
                ))}
              </div>
            )}
          </Panel>
        </>
      )}
    </div>
  );
}
