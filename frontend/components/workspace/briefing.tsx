"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useWorkspace } from "./workspace-context";
import { SeverityChip, fmtRelative } from "./format";

export function Briefing() {
  const { runCommand } = useWorkspace();
  const {
    data: briefing,
    isLoading: briefingLoading,
    error: briefingError,
    refetch: refetchBriefing,
  } = useQuery({
    queryKey: ["executive-briefing"],
    queryFn: () => api.executiveBriefing(),
  });
  const { data: alerts, error: alertsError } = useQuery({
    queryKey: ["executive-alerts"],
    queryFn: () => api.executiveAlerts(),
  });

  if (briefingLoading) {
    return (
      <section className="flex h-full flex-col border-r border-accent/20 bg-panel/70 p-3 glass-strong">
        <div className="animate-soft-pulse text-mute2">
          <span className="font-mono text-2xs uppercase tracking-widest text-accent">
            ▸
          </span>{" "}
          loading briefing…
        </div>
      </section>
    );
  }

  if (!briefing) {
    return (
      <section className="flex h-full flex-col gap-2 border-r border-accent/20 bg-panel/70 p-3 glass-strong">
        <div className="font-mono text-2xs uppercase tracking-widest text-red">
          briefing failed to load
        </div>
        <div className="break-words text-xs text-muted">
          {(briefingError as Error | null)?.message ?? "unknown error"}
        </div>
        <button
          onClick={() => refetchBriefing()}
          className="mt-1 self-start border border-border2 bg-panel2 px-2 py-1 font-mono text-2xs uppercase tracking-wider text-ink hover:border-accent hover:text-accent"
        >
          retry
        </button>
      </section>
    );
  }

  const m = briefing.metrics;
  return (
    <section className="relative flex h-full min-h-0 flex-col border-r border-accent/20 bg-panel/70 glass-strong animate-fade-in">
      <div className="pointer-events-none absolute inset-y-0 right-0 w-px bg-gradient-to-b from-transparent via-accent/40 to-transparent" />

      <header className="flex items-center justify-between border-b border-border/80 px-3 py-2">
        <div>
          <div className="flex items-center gap-2 font-mono text-2xs uppercase tracking-[0.3em] text-accent/70">
            <span className="inline-block h-1.5 w-1.5 animate-soft-pulse rounded-full bg-accent" />
            input domains
          </div>
          <div className="mt-0.5 text-md font-semibold text-inkhi">
            {briefing.headline}
          </div>
        </div>
        <button
          onClick={() => runCommand("executive briefing")}
          className="border border-border2 bg-panel2 px-2 py-1 font-mono text-2xs uppercase tracking-wider text-ink hover:border-accent hover:text-accent hover:shadow-glow-sm"
        >
          full brief
        </button>
      </header>

      <div className="flex-1 overflow-y-auto">
        <div className="grid grid-cols-2 gap-px bg-border/60 p-px">
          <Metric
            label="Capital"
            value={m.capital_active}
            sub={`${m.capital_overdue} overdue`}
            tone={m.capital_overdue ? "red" : undefined}
          />
          <Metric
            label="Programs"
            value={m.programs_active}
            sub={`${m.programs_high_value} hi-value`}
          />
          <Metric
            label="Market"
            value={m.market_accounts}
            sub={`${m.market_follow_ups_due} due`}
            tone={m.market_follow_ups_due ? "amber" : undefined}
          />
          <Metric
            label="Suppliers"
            value={m.suppliers_qualified}
            sub={`${m.suppliers_total} total`}
          />
          <Metric
            label="Approvals"
            value={m.capital_pending_approvals}
            tone={m.capital_pending_approvals ? "amber" : undefined}
          />
          <Metric
            label="Engine"
            value={m.engine_writes_pending}
            sub={`${m.engine_writes_failed} failed`}
            tone={m.engine_writes_failed ? "red" : undefined}
          />
        </div>

        <div className="border-t border-border px-3 py-2">
          <SectionLabel>narrative</SectionLabel>
          <ul className="mt-1 flex flex-col gap-0.5 text-sm text-mute2">
            {briefing.narrative.slice(0, 6).map((n, i) => (
              <li key={i} className="leading-snug">
                <span className="text-accent/60">·</span> {n}
              </li>
            ))}
          </ul>
        </div>

        {briefing.top_risks.length > 0 && (
          <div className="border-t border-border px-3 py-2">
            <div className="mb-1 flex items-center justify-between">
              <SectionLabel>top risks</SectionLabel>
              <button
                onClick={() => runCommand("show alerts")}
                className="font-mono text-2xs uppercase tracking-wider text-muted hover:text-accent"
              >
                all ›
              </button>
            </div>
            <div className="flex flex-col">
              {briefing.top_risks.slice(0, 4).map((r) => (
                <div
                  key={r.id}
                  className="flex items-center justify-between border-b border-border/60 py-1 text-sm last:border-b-0"
                >
                  <div className="flex items-center gap-2">
                    <SeverityChip severity={r.severity} />
                    <span className="truncate text-ink">{r.title}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {alertsError && (
          <div className="border-t border-border px-3 py-2 text-2xs text-red">
            alerts unavailable · {(alertsError as Error).message}
          </div>
        )}

        {alerts && alerts.alerts.length > 0 && (
          <div className="border-t border-border px-3 py-2">
            <SectionLabel>alerts · {alerts.total}</SectionLabel>
            <div className="mt-1 flex flex-wrap gap-1.5 text-2xs font-mono">
              <span className="chip border-red/50 bg-red/10 text-red">
                crit {alerts.counts_by_severity.critical ?? 0}
              </span>
              <span className="chip border-amber/50 bg-amber/10 text-amber">
                warn {alerts.counts_by_severity.warn ?? 0}
              </span>
              <span className="chip border-accent/40 bg-accent/10 text-accent">
                info {alerts.counts_by_severity.info ?? 0}
              </span>
            </div>
          </div>
        )}

        <div className="border-t border-border px-3 py-2 pb-4 font-mono text-2xs uppercase tracking-wider text-muted">
          generated {fmtRelative(briefing.generated_at)}
        </div>
      </div>
    </section>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 font-mono text-2xs uppercase tracking-[0.25em] text-accent/70">
      <span>›</span>
      <span>{children}</span>
    </div>
  );
}

function Metric({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: number;
  sub?: string;
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
  const glow =
    tone === "red"
      ? "hover:shadow-glow-red"
      : tone === "amber"
      ? "hover:shadow-glow-amber"
      : "hover:shadow-glow-sm";
  return (
    <div
      className={`group relative bg-panel/90 px-2 py-1.5 transition-all ${glow}`}
    >
      <div className="font-mono text-2xs uppercase tracking-[0.2em] text-muted">
        {label}
      </div>
      <div className={`mt-0.5 font-mono text-lg tabular-nums ${color}`}>
        {value}
      </div>
      {sub && (
        <div className="font-mono text-2xs uppercase tracking-wider text-muted">
          {sub}
        </div>
      )}
    </div>
  );
}
