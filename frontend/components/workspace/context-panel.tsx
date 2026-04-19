"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useWorkspace, type SelectedEntity } from "./workspace-context";
import { StatusDot, fmtRelative } from "./format";
import type { ActionItem } from "@/types/api";

export function ContextPanel() {
  const { selected, setSelected, runCommand } = useWorkspace();

  if (!selected) {
    return <EmptyContext />;
  }

  return (
    <aside className="relative flex h-full flex-col border-l border-accent/20 bg-panel/70 glass-strong animate-slide-in-right">
      <div className="pointer-events-none absolute inset-y-0 left-0 w-px bg-gradient-to-b from-transparent via-accent/40 to-transparent" />
      <div className="flex items-center justify-between border-b border-border/80 px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="chip-accent">{selected.kind}</span>
          <span className="font-mono text-2xs text-mute2">
            {selected.ref ?? selected.id}
          </span>
        </div>
        <button
          onClick={() => setSelected(null)}
          className="text-2xs font-mono uppercase tracking-wider text-muted hover:text-accent"
          title="Close (Esc)"
        >
          close · esc
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {selected.kind === "action" && selected.action && (
          <ActionDetail
            item={selected.action}
            onRunCommand={(c) => runCommand(c)}
          />
        )}
        {selected.kind === "entity" && (
          <EntityDetail
            entityType={selected.entityType!}
            entityId={selected.entityId!}
            label={selected.label}
            onRunCommand={(c) => runCommand(c)}
          />
        )}
      </div>
    </aside>
  );
}

function EmptyContext() {
  const { data: metrics } = useQuery({
    queryKey: ["executive-briefing-metrics"],
    queryFn: () => api.executiveBriefing(),
  });
  const m = metrics?.metrics;
  return (
    <aside className="relative flex h-full flex-col border-l border-accent/20 bg-panel/70 glass-strong">
      <div className="pointer-events-none absolute inset-y-0 left-0 w-px bg-gradient-to-b from-transparent via-accent/40 to-transparent" />
      <div className="flex items-center justify-between border-b border-border/80 px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-muted" />
          <span className="font-mono text-2xs uppercase tracking-[0.3em] text-mute2">
            context · idle
          </span>
        </div>
        <span className="font-mono text-2xs uppercase tracking-wider text-muted">
          tac · overview
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-3 text-sm">
        <div className="mb-3 border-l-2 border-accent/40 pl-2 text-xs text-mute2">
          Select a row or entity to load its detail. Nothing navigates away.
        </div>

        {m && (
          <>
            <SectionLabel>capital</SectionLabel>
            <div className="grid grid-cols-2 gap-1.5">
              <Stat label="Active" value={m.capital_active} />
              <Stat label="Overdue" value={m.capital_overdue} tone="red" />
              <Stat label="Approvals" value={m.capital_pending_approvals} tone="amber" />
            </div>

            <SectionLabel>programs</SectionLabel>
            <div className="grid grid-cols-2 gap-1.5">
              <Stat label="Active" value={m.programs_active} />
              <Stat label="Overdue" value={m.programs_overdue} tone="red" />
              <Stat label="Hi-value" value={m.programs_high_value} tone="blue" />
            </div>

            <SectionLabel>market</SectionLabel>
            <div className="grid grid-cols-2 gap-1.5">
              <Stat label="Accounts" value={m.market_accounts} />
              <Stat
                label="Follow-ups"
                value={m.market_follow_ups_due}
                tone="amber"
              />
            </div>

            <SectionLabel>supply & engine</SectionLabel>
            <div className="grid grid-cols-2 gap-1.5">
              <Stat
                label="Suppliers"
                value={m.suppliers_qualified}
                tone="green"
              />
              <Stat label="Total" value={m.suppliers_total} />
              <Stat
                label="Engine"
                value={m.engine_writes_pending}
                tone="amber"
              />
              <Stat
                label="Failed"
                value={m.engine_writes_failed}
                tone="red"
              />
            </div>
          </>
        )}
      </div>
    </aside>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-1 mt-3 flex items-center gap-2 font-mono text-2xs uppercase tracking-[0.25em] text-accent/70">
      <span>›</span>
      <span>{children}</span>
      <span className="h-px flex-1 bg-border" />
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "red" | "amber" | "green" | "blue";
}) {
  const color =
    tone === "red"
      ? "text-red"
      : tone === "amber"
      ? "text-amber"
      : tone === "green"
      ? "text-green"
      : tone === "blue"
      ? "text-blue"
      : "text-inkhi";
  const accent =
    tone === "red"
      ? "border-red/30"
      : tone === "amber"
      ? "border-amber/30"
      : tone === "green"
      ? "border-green/30"
      : tone === "blue"
      ? "border-blue/30"
      : "border-border2";
  return (
    <div
      className={`border bg-panel2/60 px-2 py-1 backdrop-blur-sm ${accent} animate-fade-in`}
    >
      <div className="text-2xs font-mono uppercase tracking-wider text-muted">
        {label}
      </div>
      <div className={`mt-0.5 font-mono text-md tabular-nums ${color}`}>
        {value}
      </div>
    </div>
  );
}

function ActionDetail({
  item,
  onRunCommand,
}: {
  item: ActionItem;
  onRunCommand: (text: string) => void;
}) {
  const grouped = actionButtonsFor(item);
  return (
    <div className="flex flex-col gap-3 p-3 text-sm animate-fade-in">
      <div>
        <div className="flex items-center gap-2 text-2xs font-mono uppercase tracking-wider text-muted">
          <StatusDot tone={priorityTone(item.priority_score)} />
          <span className="text-accent">{item.domain}</span>
          <span>·</span>
          <span>{item.kind}</span>
          <span>·</span>
          <span className="text-ink">P{Math.round(item.priority_score)}</span>
        </div>
        <h2 className="mt-1 text-md font-semibold text-inkhi">{item.title}</h2>
        {item.description && (
          <p className="mt-2 whitespace-pre-wrap text-mute2">
            {item.description}
          </p>
        )}
      </div>

      <div>
        <SectionLabel>telemetry</SectionLabel>
        <dl className="grid grid-cols-[90px_1fr] gap-y-1 text-xs">
          <Row label="source" value={item.source_label} />
          <Row label="due" value={fmtRelative(item.due_at)} />
          <Row label="status" value={item.status ?? "—"} />
          <Row
            label="entity"
            value={
              item.related_entity_type
                ? `${item.related_entity_type} #${item.related_entity_id}`
                : "—"
            }
          />
          <Row label="link" value={item.link_hint ?? "—"} />
        </dl>
      </div>

      {grouped.length > 0 && (
        <div>
          <SectionLabel>actions</SectionLabel>
          <div className="grid grid-cols-2 gap-1.5">
            {grouped.map((a) => (
              <button
                key={a.label}
                onClick={() => onRunCommand(a.command)}
                className="group flex items-center justify-between border border-border2 bg-panel2/60 px-2 py-1.5 text-left font-mono text-2xs uppercase tracking-wider text-ink transition-all hover:border-accent hover:bg-accent/10 hover:text-accent hover:shadow-glow-sm"
              >
                <span>{a.label}</span>
                <span className="text-accent/50 group-hover:text-accent">▸</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function actionButtonsFor(item: ActionItem): Array<{
  label: string;
  command: string;
}> {
  const out: Array<{ label: string; command: string }> = [];
  if (item.domain === "capital") {
    out.push({
      label: "draft follow-up",
      command: `draft follow-up for opportunity ${item.related_entity_id}`,
    });
    out.push({
      label: "brief",
      command: `brief on opportunity ${item.related_entity_id}`,
    });
  }
  if (item.domain === "program") {
    out.push({
      label: "show program",
      command: `show program ${item.related_entity_id}`,
    });
  }
  if (item.domain === "market") {
    out.push({
      label: "review campaign",
      command: `show campaign ${item.related_entity_id}`,
    });
  }
  if (item.domain === "supplier") {
    out.push({
      label: "show supplier",
      command: `show supplier ${item.related_entity_id}`,
    });
  }
  if (item.domain === "approval") {
    out.push({ label: "review approvals", command: "review approvals" });
  }
  if (item.domain === "engine") {
    out.push({ label: "show engine writes", command: "list engine writes" });
  }
  return out;
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <>
      <dt className="font-mono text-2xs uppercase tracking-wider text-muted">
        {label}
      </dt>
      <dd className="text-mute2">{value}</dd>
    </>
  );
}

function priorityTone(p: number): "red" | "amber" | "green" | "blue" {
  if (p >= 80) return "red";
  if (p >= 50) return "amber";
  if (p >= 20) return "blue";
  return "green";
}

function EntityDetail({
  entityType,
  entityId,
  label,
  onRunCommand,
}: {
  entityType: string;
  entityId: number;
  label?: string;
  onRunCommand: (text: string) => void;
}) {
  return (
    <div className="flex flex-col gap-3 p-3 text-sm animate-fade-in">
      <div>
        <div className="text-2xs font-mono uppercase tracking-wider text-muted">
          <span className="text-accent">{entityType}</span> · #{entityId}
        </div>
        <h2 className="mt-1 text-md font-semibold text-inkhi">
          {label ?? `${entityType} #${entityId}`}
        </h2>
      </div>
      <SectionLabel>actions</SectionLabel>
      <div className="grid grid-cols-2 gap-1.5">
        <ActionButton onClick={() => onRunCommand(`show ${entityType} ${entityId}`)}>
          show
        </ActionButton>
        {entityType === "opportunity" && (
          <>
            <ActionButton
              onClick={() => onRunCommand(`brief on opportunity ${entityId}`)}
            >
              brief
            </ActionButton>
            <ActionButton
              onClick={() =>
                onRunCommand(`draft follow-up for opportunity ${entityId}`)
              }
            >
              draft
            </ActionButton>
          </>
        )}
      </div>
      <div className="mt-2 border-l-2 border-accent/40 pl-2 text-2xs text-muted">
        Run any command scoped to this entity from the command bar (⌘K).
      </div>
    </div>
  );
}

function ActionButton({
  children,
  onClick,
}: {
  children: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="group flex items-center justify-between border border-border2 bg-panel2/60 px-2 py-1.5 font-mono text-2xs uppercase tracking-wider text-ink transition-all hover:border-accent hover:bg-accent/10 hover:text-accent hover:shadow-glow-sm"
    >
      <span>{children}</span>
      <span className="text-accent/50 group-hover:text-accent">▸</span>
    </button>
  );
}

export type { SelectedEntity };
