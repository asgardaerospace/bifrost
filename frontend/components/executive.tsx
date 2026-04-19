"use client";

import Link from "next/link";
import type {
  ActionItem,
  ActionQueue,
  Alert,
  AlertBundle,
  DailyBriefing,
} from "@/types/api";
import { Empty, Panel, Pill, formatDate, relative } from "@/components/ui";

const DOMAIN_TONE: Record<
  string,
  "default" | "warn" | "danger" | "ok" | "accent"
> = {
  capital: "accent",
  market: "default",
  program: "warn",
  supplier: "default",
  approval: "warn",
  engine: "danger",
};

function severityTone(
  s: string,
): "default" | "warn" | "danger" | "ok" | "accent" {
  if (s === "critical") return "danger";
  if (s === "warn") return "warn";
  return "default";
}

export function ActionRow({ a }: { a: ActionItem }) {
  return (
    <li className="flex items-start justify-between gap-3 py-2">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="tabular-nums font-mono text-[11px] text-muted">
            p{a.priority_score}
          </span>
          <div className="truncate font-medium">{a.title}</div>
        </div>
        {a.description && (
          <div className="mt-0.5 truncate text-xs text-muted">
            {a.description}
          </div>
        )}
        <div className="mt-0.5 text-[11px] text-muted">
          {a.source_label}
          {a.due_at ? ` · due ${formatDate(a.due_at)}` : ""}
        </div>
      </div>
      <div className="flex flex-col items-end gap-1">
        <Pill tone={DOMAIN_TONE[a.domain] ?? "default"}>{a.domain}</Pill>
        {a.link_hint && (
          <Link
            href={a.link_hint}
            className="font-mono text-[11px] uppercase tracking-widest text-muted hover:text-ink"
          >
            open →
          </Link>
        )}
      </div>
    </li>
  );
}

export function ActionQueueView({ queue }: { queue: ActionQueue }) {
  if (queue.items.length === 0) return <Empty>Queue is clear.</Empty>;
  return (
    <ul className="divide-y divide-border">
      {queue.items.map((a) => (
        <ActionRow key={a.id} a={a} />
      ))}
    </ul>
  );
}

export function AlertRow({ a }: { a: Alert }) {
  return (
    <li className="flex items-start justify-between gap-3 py-2">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <Pill tone={severityTone(a.severity)}>{a.severity}</Pill>
          <div className="truncate font-medium">{a.title}</div>
        </div>
        <div className="mt-0.5 text-xs text-muted">{a.description}</div>
        <div className="mt-0.5 text-[11px]">
          <span className="text-muted">Recommended · </span>
          {a.recommended_action}
        </div>
      </div>
      <div className="flex flex-col items-end gap-1">
        <Pill tone={DOMAIN_TONE[a.domain] ?? "default"}>{a.domain}</Pill>
        {a.link_hint && (
          <Link
            href={a.link_hint}
            className="font-mono text-[11px] uppercase tracking-widest text-muted hover:text-ink"
          >
            open →
          </Link>
        )}
      </div>
    </li>
  );
}

export function AlertListView({ bundle }: { bundle: AlertBundle }) {
  if (bundle.alerts.length === 0) return <Empty>No alerts.</Empty>;
  return (
    <ul className="divide-y divide-border">
      {bundle.alerts.map((a) => (
        <AlertRow key={a.id} a={a} />
      ))}
    </ul>
  );
}

export function BriefingView({ briefing }: { briefing: DailyBriefing }) {
  const m = briefing.metrics;
  return (
    <div className="space-y-4">
      <header>
        <h2 className="text-base font-semibold">{briefing.headline}</h2>
        <p className="mt-1 text-[11px] text-muted">
          Generated {relative(briefing.generated_at)}
        </p>
      </header>

      {briefing.narrative.length > 0 && (
        <Panel title="Narrative">
          <ul className="list-disc pl-5 text-sm text-ink/90">
            {briefing.narrative.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </Panel>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <MetricTile label="Capital · active" value={m.capital_active} />
        <MetricTile label="Capital · overdue" value={m.capital_overdue} />
        <MetricTile label="Programs · active" value={m.programs_active} />
        <MetricTile label="Programs · overdue" value={m.programs_overdue} />
        <MetricTile label="Market · follow-ups" value={m.market_follow_ups_due} />
        <MetricTile label="Suppliers · qualified" value={m.suppliers_qualified} />
        <MetricTile label="Approvals · pending" value={m.capital_pending_approvals} />
        <MetricTile label="Engine · failed" value={m.engine_writes_failed} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Panel title="Top actions">
          {briefing.top_actions.length === 0 ? (
            <Empty>Nothing queued.</Empty>
          ) : (
            <ul className="divide-y divide-border">
              {briefing.top_actions.map((a) => (
                <ActionRow key={a.id} a={a} />
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Top risks">
          {briefing.top_risks.length === 0 ? (
            <Empty>No risks flagged.</Empty>
          ) : (
            <ul className="divide-y divide-border">
              {briefing.top_risks.map((a) => (
                <AlertRow key={a.id} a={a} />
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {briefing.sections.map((s) => (
          <Panel
            key={`${s.domain}-${s.title}`}
            title={s.title}
            right={<Pill tone={DOMAIN_TONE[s.domain] ?? "default"}>{s.domain}</Pill>}
          >
            <p className="mb-2 text-[11px] text-muted">{s.headline}</p>
            {s.items.length === 0 ? (
              <Empty>—</Empty>
            ) : (
              <ul className="divide-y divide-border">
                {s.items.map((it, idx) => (
                  <li
                    key={`${it.related_entity_type}-${it.related_entity_id}-${idx}`}
                    className="flex items-center justify-between py-2"
                  >
                    <div className="min-w-0">
                      <div className="truncate font-medium">{it.label}</div>
                      {it.subtitle && (
                        <div className="truncate text-xs text-muted">
                          {it.subtitle}
                        </div>
                      )}
                    </div>
                    <div className="flex flex-col items-end gap-1">
                      {it.badge && <Pill tone="default">{it.badge}</Pill>}
                      {it.link_hint && (
                        <Link
                          href={it.link_hint}
                          className="font-mono text-[11px] uppercase tracking-widest text-muted hover:text-ink"
                        >
                          open →
                        </Link>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        ))}
      </div>
    </div>
  );
}

function MetricTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-border bg-bg/40 px-3 py-2">
      <div className="font-mono text-[10px] uppercase tracking-widest text-muted">
        {label}
      </div>
      <div className="mt-1 text-xl tabular-nums">{value}</div>
    </div>
  );
}
