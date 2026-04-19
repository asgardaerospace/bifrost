"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useWorkspace, type SelectedEntity } from "./workspace-context";
import { StatusDot, SeverityChip, fmtRelative, fmtDate } from "./format";
import type { ActionItem } from "@/types/api";

export function ContextPanel() {
  const { selected, setSelected, runCommand } = useWorkspace();

  if (!selected) {
    return <EmptyContext />;
  }

  return (
    <aside className="flex h-full flex-col border-l border-border bg-panel">
      <div className="flex items-center justify-between border-b border-border px-4 py-2">
        <div className="flex items-center gap-2">
          <span className="chip">{selected.kind}</span>
          <span className="text-xs text-mute2">
            {selected.ref ?? selected.id}
          </span>
        </div>
        <button
          onClick={() => setSelected(null)}
          className="text-2xs font-mono uppercase tracking-wider text-muted hover:text-ink"
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
    <aside className="flex h-full flex-col border-l border-border bg-panel">
      <div className="border-b border-border px-4 py-2 text-2xs font-mono uppercase tracking-wider text-muted">
        context · idle
      </div>
      <div className="flex-1 overflow-y-auto p-4 text-sm">
        <div className="text-mute2">
          Select a row or entity to load its detail here. Nothing navigates
          away.
        </div>
        {m && (
          <div className="mt-4 grid grid-cols-2 gap-2">
            <Stat label="Capital active" value={m.capital_active} />
            <Stat label="Capital overdue" value={m.capital_overdue} tone="red" />
            <Stat label="Programs active" value={m.programs_active} />
            <Stat
              label="Programs overdue"
              value={m.programs_overdue}
              tone="red"
            />
            <Stat label="Market accts" value={m.market_accounts} />
            <Stat
              label="Follow-ups due"
              value={m.market_follow_ups_due}
              tone="amber"
            />
            <Stat
              label="Suppliers qual."
              value={m.suppliers_qualified}
              tone="green"
            />
            <Stat
              label="Engine pending"
              value={m.engine_writes_pending}
              tone="amber"
            />
            <Stat
              label="Engine failed"
              value={m.engine_writes_failed}
              tone="red"
            />
            <Stat
              label="Approvals"
              value={m.capital_pending_approvals}
              tone="amber"
            />
          </div>
        )}
      </div>
    </aside>
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
      : "text-ink";
  return (
    <div className="border border-border bg-panel2 px-2 py-1.5">
      <div className="text-2xs font-mono uppercase tracking-wider text-muted">
        {label}
      </div>
      <div className={`mt-0.5 font-mono text-lg tabular-nums ${color}`}>
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
  return (
    <div className="flex flex-col gap-3 p-4 text-sm">
      <div>
        <div className="flex items-center gap-2 text-2xs font-mono uppercase tracking-wider text-muted">
          <StatusDot tone={priorityTone(item.priority_score)} />
          <span>{item.domain}</span>
          <span>·</span>
          <span>{item.kind}</span>
          <span>·</span>
          <span>P{Math.round(item.priority_score)}</span>
        </div>
        <h2 className="mt-1 text-md font-semibold text-inkhi">{item.title}</h2>
        {item.description && (
          <p className="mt-2 whitespace-pre-wrap text-mute2">
            {item.description}
          </p>
        )}
      </div>

      <dl className="grid grid-cols-[110px_1fr] gap-y-1 border-t border-border pt-3 text-xs">
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

      <div className="flex flex-wrap gap-2 border-t border-border pt-3">
        {actionButtonsFor(item).map((a) => (
          <button
            key={a.label}
            onClick={() => onRunCommand(a.command)}
            className="border border-border2 bg-panel2 px-2 py-1 font-mono text-2xs uppercase tracking-wider text-ink hover:border-blue hover:text-blue"
          >
            {a.label}
          </button>
        ))}
      </div>
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
    <div className="flex flex-col gap-3 p-4 text-sm">
      <div>
        <div className="text-2xs font-mono uppercase tracking-wider text-muted">
          {entityType} · #{entityId}
        </div>
        <h2 className="mt-1 text-md font-semibold text-inkhi">
          {label ?? `${entityType} #${entityId}`}
        </h2>
      </div>
      <div className="flex flex-wrap gap-2 border-t border-border pt-3">
        <button
          onClick={() => onRunCommand(`show ${entityType} ${entityId}`)}
          className="border border-border2 bg-panel2 px-2 py-1 font-mono text-2xs uppercase tracking-wider text-ink hover:border-blue hover:text-blue"
        >
          show
        </button>
        {entityType === "opportunity" && (
          <>
            <button
              onClick={() => onRunCommand(`brief on opportunity ${entityId}`)}
              className="border border-border2 bg-panel2 px-2 py-1 font-mono text-2xs uppercase tracking-wider text-ink hover:border-blue hover:text-blue"
            >
              brief
            </button>
            <button
              onClick={() =>
                onRunCommand(`draft follow-up for opportunity ${entityId}`)
              }
              className="border border-border2 bg-panel2 px-2 py-1 font-mono text-2xs uppercase tracking-wider text-ink hover:border-blue hover:text-blue"
            >
              draft
            </button>
          </>
        )}
      </div>
      <div className="text-2xs text-muted">
        Run any command scoped to this entity from the command bar (⌘K).
      </div>
    </div>
  );
}

export type { SelectedEntity };
