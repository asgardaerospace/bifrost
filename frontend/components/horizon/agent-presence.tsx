"use client";

/**
 * Agent presence panel — Sprint 7.
 *
 * Compact, calm view of registered agents and their recent operational
 * footprint. Distinct from the existing agent rail: this is *presence*, not
 * an inspector — operators see who is in the habitat and what they're doing.
 *
 * Doctrine: agents are procedural, inspectable, aerospace-grade. Never
 * anthropomorphic, chatty, or magical. We render runs as deterministic
 * rows with status, confidence, and duration.
 */

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { Empty, Panel, Pill } from "@/components/ui";
import type {
  AgentDescriptorRead,
  AutonomyOperationRead,
} from "@/types/api";

const STATUS_TONE: Record<string, "default" | "accent" | "ok" | "warn" | "danger"> = {
  proposed: "accent",
  running: "accent",
  approved: "ok",
  executed: "ok",
  cancelled: "warn",
  failed: "danger",
  rejected: "danger",
};

function formatRelative(iso: string | null | undefined): string {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  const m = Math.round((Date.now() - t) / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 48) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}

function AgentRow({
  agent,
  runs,
}: {
  agent: AgentDescriptorRead;
  runs: AutonomyOperationRead[];
}) {
  const recent = runs.find((r) => r.agent_name === agent.name);
  const allForAgent = runs.filter((r) => r.agent_name === agent.name);
  const pending = allForAgent.filter((r) => r.status === "running").length;
  const proposed = allForAgent.filter((r) => r.status === "proposed").length;

  return (
    <div className="grid grid-cols-[1fr_auto_auto] items-center gap-3 rounded-md border border-border/70 bg-panel/60 px-3 py-2">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-mono text-2xs uppercase tracking-wider text-accent">
            {agent.name}
          </span>
          <span className="font-mono text-[10px] text-muted">v{agent.version}</span>
        </div>
        <div className="mt-0.5 truncate text-xs text-muted">
          {agent.workflow_key}
          {recent && (
            <>
              {" · "}
              <span className="text-ink">{formatRelative(recent.proposed_at)}</span>
            </>
          )}
        </div>
      </div>
      <div className="flex items-center gap-2 font-mono text-2xs uppercase tracking-wider">
        {pending > 0 && <Pill tone="accent">running {pending}</Pill>}
        {proposed > 0 && <Pill tone="warn">proposed {proposed}</Pill>}
      </div>
      <div>
        {recent ? (
          <Pill tone={STATUS_TONE[recent.status] ?? "default"}>{recent.status}</Pill>
        ) : (
          <Pill tone="default">idle</Pill>
        )}
      </div>
    </div>
  );
}

export function AgentPresence() {
  const { data: agents } = useQuery({
    queryKey: ["sprint7-agents"],
    queryFn: api.listAgents,
    refetchInterval: 60_000,
  });

  const { data: runs } = useQuery({
    queryKey: ["sprint7-agent-runs"],
    queryFn: () => api.listAgentRuns({ limit: 50 }),
    refetchInterval: 20_000,
  });

  return (
    <Panel
      title={`agent presence · ${agents?.length ?? 0}`}
      right={
        <span className="font-mono text-2xs uppercase tracking-wider text-muted">
          {(runs?.filter((r) => r.status === "running").length ?? 0)} active
        </span>
      }
    >
      {!agents || agents.length === 0 ? (
        <Empty>No registered agents.</Empty>
      ) : (
        <div className="flex flex-col gap-2">
          {agents.map((a) => (
            <AgentRow key={a.name} agent={a} runs={runs ?? []} />
          ))}
        </div>
      )}
    </Panel>
  );
}
