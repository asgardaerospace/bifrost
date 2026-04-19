"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ProgramRead } from "@/types/api";
import { Empty, Panel, Pill, Stat, formatDate } from "@/components/ui";

function money(v?: number | null) {
  if (v === null || v === undefined) return "—";
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}K`;
  return `$${v.toFixed(0)}`;
}

function stageTone(
  stage: string,
): "default" | "warn" | "danger" | "ok" | "accent" {
  switch (stage) {
    case "won":
      return "ok";
    case "lost":
      return "default";
    case "active":
      return "accent";
    case "pursuing":
      return "warn";
    default:
      return "default";
  }
}

function ProgramRows({ rows }: { rows: ProgramRead[] }) {
  if (rows.length === 0) return <Empty>No programs.</Empty>;
  return (
    <ul className="divide-y divide-border">
      {rows.map((p) => (
        <li key={p.id} className="flex items-start justify-between py-2">
          <div className="min-w-0">
            <div className="truncate font-medium">{p.name}</div>
            <div className="text-xs text-muted">
              {p.account_name ?? `account #${p.account_id}`}
              {p.owner ? ` · ${p.owner}` : ""}
              {p.next_step_due_at
                ? ` · due ${formatDate(p.next_step_due_at)}`
                : ""}
            </div>
          </div>
          <div className="flex flex-col items-end gap-1">
            <Pill tone={stageTone(p.stage)}>{p.stage}</Pill>
            <span className="text-[11px] text-muted tabular-nums">
              {money(p.estimated_value)}
            </span>
          </div>
        </li>
      ))}
    </ul>
  );
}

export default function ProgramsPage() {
  const pipeline = useQuery({
    queryKey: ["program-pipeline"],
    queryFn: api.programPipelineSummary,
  });
  const active = useQuery({
    queryKey: ["programs-active"],
    queryFn: () => api.listActivePrograms(100),
  });

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-xl font-semibold">Programs</h1>
        <p className="mt-1 text-sm text-muted">
          Contracts, pursuits, and strategic partnerships — the execution layer
          connecting accounts, opportunities, and (soon) investors.
        </p>
      </header>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Stat label="Total" value={pipeline.data?.total_programs ?? "—"} />
        <Stat label="Active" value={pipeline.data?.active_count ?? "—"} />
        <Stat label="Won" value={pipeline.data?.won_count ?? "—"} />
        <Stat
          label="High-value"
          value={pipeline.data?.high_value_count ?? "—"}
        />
        <Stat label="Overdue" value={pipeline.data?.overdue_count ?? "—"} />
      </div>

      <Panel title="Pipeline by stage">
        {pipeline.isLoading ? (
          <Empty>Loading…</Empty>
        ) : !pipeline.data || pipeline.data.stage_counts.length === 0 ? (
          <Empty>No programs yet.</Empty>
        ) : (
          <div className="grid grid-cols-3 gap-2 md:grid-cols-5">
            {pipeline.data.stage_counts.map((s) => (
              <div
                key={s.stage}
                className="rounded border border-border bg-bg/40 px-3 py-2"
              >
                <div className="font-mono text-[10px] uppercase tracking-widest text-muted">
                  {s.stage}
                </div>
                <div className="text-lg tabular-nums">{s.count}</div>
              </div>
            ))}
          </div>
        )}
      </Panel>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Panel title="Active programs">
          {active.isLoading ? (
            <Empty>Loading…</Empty>
          ) : (
            <ProgramRows rows={active.data ?? []} />
          )}
        </Panel>

        <Panel title="High-value programs">
          {pipeline.isLoading ? (
            <Empty>Loading…</Empty>
          ) : (
            <ProgramRows rows={pipeline.data?.high_value ?? []} />
          )}
        </Panel>

        <Panel title="Overdue next steps">
          {pipeline.isLoading ? (
            <Empty>Loading…</Empty>
          ) : (
            <ProgramRows rows={pipeline.data?.overdue ?? []} />
          )}
        </Panel>

        <Panel title="Active pipeline value">
          <div className="text-3xl font-semibold tabular-nums">
            {money(pipeline.data?.total_estimated_value_active)}
          </div>
          <p className="mt-1 text-xs text-muted">
            Sum of estimated_value across pursuing + active programs.
          </p>
        </Panel>
      </div>
    </div>
  );
}
