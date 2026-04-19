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
      <section className="flex h-full flex-col border-r border-border bg-panel p-3">
        <div className="text-muted">loading briefing…</div>
      </section>
    );
  }

  if (!briefing) {
    return (
      <section className="flex h-full flex-col border-r border-border bg-panel p-3 gap-2">
        <div className="font-mono text-2xs uppercase tracking-widest text-red">
          briefing failed to load
        </div>
        <div className="text-xs text-muted break-words">
          {(briefingError as Error | null)?.message ?? "unknown error"}
        </div>
        <button
          onClick={() => refetchBriefing()}
          className="mt-1 self-start border border-border2 bg-panel2 px-2 py-1 font-mono text-2xs uppercase tracking-wider text-ink hover:border-blue hover:text-blue"
        >
          retry
        </button>
      </section>
    );
  }

  const m = briefing.metrics;
  return (
    <section className="flex h-full min-h-0 flex-col border-r border-border bg-panel">
      <header className="flex items-center justify-between border-b border-border px-3 py-2">
        <div>
          <div className="font-mono text-2xs uppercase tracking-widest text-mute2">
            executive briefing
          </div>
          <div className="mt-0.5 text-md font-semibold text-inkhi">
            {briefing.headline}
          </div>
        </div>
        <button
          onClick={() => runCommand("executive briefing")}
          className="border border-border2 bg-panel2 px-2 py-1 font-mono text-2xs uppercase tracking-wider text-ink hover:border-blue hover:text-blue"
        >
          full brief
        </button>
      </header>

      <div className="flex-1 overflow-y-auto">
        <div className="grid grid-cols-2 gap-px bg-border p-px">
          <Metric label="Capital" value={m.capital_active} sub={`${m.capital_overdue} overdue`} tone={m.capital_overdue ? "red" : undefined} />
          <Metric label="Programs" value={m.programs_active} sub={`${m.programs_high_value} hi-value`} />
          <Metric label="Market" value={m.market_accounts} sub={`${m.market_follow_ups_due} due`} tone={m.market_follow_ups_due ? "amber" : undefined} />
          <Metric label="Suppliers" value={m.suppliers_qualified} sub={`${m.suppliers_total} total`} />
          <Metric label="Approvals" value={m.capital_pending_approvals} tone={m.capital_pending_approvals ? "amber" : undefined} />
          <Metric label="Engine" value={m.engine_writes_pending} sub={`${m.engine_writes_failed} failed`} tone={m.engine_writes_failed ? "red" : undefined} />
        </div>

        <div className="border-t border-border px-3 py-2">
          <div className="font-mono text-2xs uppercase tracking-wider text-muted">
            narrative
          </div>
          <ul className="mt-1 flex flex-col gap-0.5 text-sm text-mute2">
            {briefing.narrative.slice(0, 6).map((n, i) => (
              <li key={i} className="leading-snug">
                {n}
              </li>
            ))}
          </ul>
        </div>

        {briefing.top_risks.length > 0 && (
          <div className="border-t border-border px-3 py-2">
            <div className="mb-1 flex items-center justify-between">
              <span className="font-mono text-2xs uppercase tracking-wider text-muted">
                top risks
              </span>
              <button
                onClick={() => runCommand("show alerts")}
                className="font-mono text-2xs uppercase tracking-wider text-muted hover:text-ink"
              >
                all ›
              </button>
            </div>
            <div className="flex flex-col">
              {briefing.top_risks.slice(0, 4).map((r) => (
                <div
                  key={r.id}
                  className="flex items-center justify-between border-b border-border py-1 text-sm last:border-b-0"
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
            <div className="font-mono text-2xs uppercase tracking-wider text-muted">
              alerts · {alerts.total}
            </div>
            <div className="mt-1 flex flex-wrap gap-1.5 text-2xs font-mono">
              <span className="chip border-red text-red">
                crit {alerts.counts_by_severity.critical ?? 0}
              </span>
              <span className="chip border-amber text-amber">
                warn {alerts.counts_by_severity.warn ?? 0}
              </span>
              <span className="chip border-blue text-blue">
                info {alerts.counts_by_severity.info ?? 0}
              </span>
            </div>
          </div>
        )}

        <div className="border-t border-border px-3 py-2 pb-4 text-2xs text-muted">
          generated {fmtRelative(briefing.generated_at)}
        </div>
      </div>
    </section>
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
  return (
    <div className="bg-panel px-2 py-1.5">
      <div className="font-mono text-2xs uppercase tracking-wider text-muted">
        {label}
      </div>
      <div className={`mt-0.5 font-mono text-lg tabular-nums ${color}`}>
        {value}
      </div>
      {sub && <div className="text-2xs text-muted">{sub}</div>}
    </div>
  );
}
