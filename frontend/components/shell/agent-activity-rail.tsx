"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type {
  AgentDescriptorRead,
  AgentRunReport,
  AutonomyOperationRead,
} from "@/types/api";

const STATUS_TONE: Record<string, string> = {
  proposed: "text-accent",
  weak: "text-mute2",
  failed: "text-red",
  cancelled: "text-amber",
  running: "text-cyan",
  approved: "text-green",
  rejected: "text-red",
  executed: "text-green",
};

function relTime(iso: string | null | undefined) {
  if (!iso) return "—";
  const d = new Date(iso);
  const diff = Date.now() - d.getTime();
  const m = Math.round(diff / 60_000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}

function AgentRosterCard({
  agent,
  onRun,
  isRunning,
}: {
  agent: AgentDescriptorRead;
  onRun: () => void;
  isRunning: boolean;
}) {
  return (
    <article className="rounded-md border border-border/60 bg-panel2/40 p-3">
      <header className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="font-mono text-xs uppercase tracking-wider text-accent">
            {agent.name}
          </div>
          <div className="mt-0.5 font-mono text-[10px] text-mute2">
            v{agent.version} · {agent.workflow_key}
          </div>
        </div>
        <button
          type="button"
          onClick={onRun}
          disabled={isRunning}
          className="chip-accent rounded-md px-3 py-1 font-mono text-[10px] uppercase tracking-widest hover:bg-accent/30 disabled:opacity-40"
        >
          {isRunning ? "…" : "run"}
        </button>
      </header>
      <p className="mt-2 line-clamp-2 text-xs text-mute2">{agent.purpose}</p>
      <div className="mt-2 grid grid-cols-2 gap-1 font-mono text-[10px] text-mute2">
        <div>
          <div className="text-mute2/80">stages</div>
          <div className="text-ink">{agent.stages.length}</div>
        </div>
        <div>
          <div className="text-mute2/80">conf ≥</div>
          <div className="text-ink">{agent.confidence_threshold}</div>
        </div>
        <div className="col-span-2">
          <div className="text-mute2/80">domains</div>
          <div className="text-ink/80">
            {agent.accessible_domains.join(" · ")}
          </div>
        </div>
      </div>
      <div className="mt-2 border-t border-border/60 pt-2 font-mono text-[10px]">
        <div className="text-amber/80">approval-gated</div>
        <ul className="mt-1 flex flex-wrap gap-1">
          {agent.required_approvals.map((a) => (
            <li key={a} className="chip text-amber/90">
              {a}
            </li>
          ))}
        </ul>
      </div>
    </article>
  );
}

function AgentRunRow({
  run,
  onSelect,
  isSelected,
}: {
  run: AutonomyOperationRead;
  onSelect: () => void;
  isSelected: boolean;
}) {
  const tone = STATUS_TONE[run.status] ?? "text-mute2";
  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        className={
          "w-full rounded-md border bg-panel2/40 p-2 text-left transition-colors " +
          (isSelected
            ? "border-accent bg-panel3/70 shadow-glow-sm"
            : "border-border/60 hover:border-accent/40 hover:bg-panel3/60")
        }
      >
        <div className="flex items-center justify-between font-mono text-[10px] uppercase tracking-wider">
          <span className="truncate text-accent/90">{run.agent_name}</span>
          <span className={tone}>{run.status}</span>
        </div>
        <div className="mt-0.5 flex items-center justify-between font-mono text-[10px] text-mute2">
          <span>#{run.id}</span>
          <span>{relTime(run.proposed_at ?? run.created_at)}</span>
        </div>
        <div className="mt-1 flex items-center gap-2 font-mono text-[10px] text-mute2">
          <span>conf {run.confidence_score}</span>
          {run.workflow_key && <span>· {run.workflow_key}</span>}
          {run.trigger && (
            <span className="ml-auto truncate" title={run.trigger}>
              {run.trigger}
            </span>
          )}
        </div>
      </button>
    </li>
  );
}

export function AgentActivityRail({
  selectedRunId,
  onSelectRun,
}: {
  selectedRunId: number | null;
  onSelectRun: (id: number) => void;
}) {
  const qc = useQueryClient();

  const { data: agents, isLoading: agentsLoading } = useQuery({
    queryKey: ["agents", "registry"],
    queryFn: () => api.listAgents(),
    staleTime: 60_000,
  });

  const { data: runs, isLoading: runsLoading } = useQuery({
    queryKey: ["agent-runs", "all"],
    queryFn: () => api.listAgentRuns({ limit: 30 }),
    staleTime: 10_000,
    refetchInterval: 15_000,
  });

  const runAgent = useMutation({
    mutationFn: (name: string) =>
      api.runAgent(name, { trigger: "operator-manual" }),
    onSuccess: (report: AgentRunReport) => {
      qc.invalidateQueries({ queryKey: ["agent-runs"] });
      qc.invalidateQueries({ queryKey: ["proposed-actions"] });
      onSelectRun(report.operation_id);
    },
  });

  return (
    <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <div className="rounded-lg border border-border/60 bg-panel/60">
        <header className="flex items-center justify-between border-b border-border/60 px-4 py-3">
          <span className="font-mono text-2xs uppercase tracking-widest text-accent/80">
            ▸ agent roster
          </span>
          <span className="font-mono text-2xs text-mute2">
            {agents?.length ?? 0} registered
          </span>
        </header>
        <div className="grid grid-cols-1 gap-2 p-3">
          {agentsLoading && (
            <div className="px-2 py-4 font-mono text-2xs text-mute2 animate-soft-pulse">
              ▸ loading registry…
            </div>
          )}
          {(agents ?? []).map((a) => (
            <AgentRosterCard
              key={a.name}
              agent={a}
              isRunning={
                runAgent.isPending && runAgent.variables === a.name
              }
              onRun={() => runAgent.mutate(a.name)}
            />
          ))}
        </div>
      </div>

      <div className="rounded-lg border border-border/60 bg-panel/60">
        <header className="flex items-center justify-between border-b border-border/60 px-4 py-3">
          <span className="font-mono text-2xs uppercase tracking-widest text-accent/80">
            ▸ recent runs
          </span>
          <span className="font-mono text-2xs text-mute2">
            {runs?.length ?? 0} runs
          </span>
        </header>
        <ul className="flex flex-col gap-1.5 p-3">
          {runsLoading && (
            <li className="px-2 py-4 font-mono text-2xs text-mute2 animate-soft-pulse">
              ▸ loading runs…
            </li>
          )}
          {!runsLoading && (runs?.length ?? 0) === 0 && (
            <li className="px-2 py-4 text-center font-mono text-2xs text-mute2">
              no agent runs yet · click run to dispatch one
            </li>
          )}
          {(runs ?? []).map((r) => (
            <AgentRunRow
              key={r.id}
              run={r}
              isSelected={r.id === selectedRunId}
              onSelect={() => onSelectRun(r.id)}
            />
          ))}
        </ul>
      </div>
    </section>
  );
}
