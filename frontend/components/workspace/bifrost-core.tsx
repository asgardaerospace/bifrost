"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useWorkspace } from "./workspace-context";

export function BifrostCore() {
  const { runCommand, running } = useWorkspace();
  const { data: briefing } = useQuery({
    queryKey: ["executive-briefing"],
    queryFn: () => api.executiveBriefing(),
  });
  const { data: queue } = useQuery({
    queryKey: ["action-queue", "all"],
    queryFn: () => api.executiveActionQueue({ limit: 80 }),
  });
  const { data: alerts } = useQuery({
    queryKey: ["executive-alerts"],
    queryFn: () => api.executiveAlerts(),
  });

  const m = briefing?.metrics;
  const activeActions = queue?.items.length ?? 0;
  const activePrograms = m?.programs_active ?? 0;
  const risk =
    (alerts?.counts_by_severity.critical ?? 0) > 0
      ? "critical"
      : (alerts?.counts_by_severity.warn ?? 0) > 0
      ? "warning"
      : "nominal";

  const riskTone =
    risk === "critical"
      ? "text-red"
      : risk === "warning"
      ? "text-amber"
      : "text-green";

  const ringColor =
    risk === "critical"
      ? "rgba(255,90,107,0.55)"
      : risk === "warning"
      ? "rgba(240,180,41,0.5)"
      : "rgba(34,211,238,0.5)";

  return (
    <section className="relative flex min-h-0 flex-col border-x border-border bg-panel/60 panel-edge">
      <div className="flex items-center justify-between border-b border-border/80 px-3 py-1.5">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span
              className={`absolute inline-flex h-full w-full rounded-full opacity-70 animate-soft-pulse ${
                risk === "critical"
                  ? "bg-red"
                  : risk === "warning"
                  ? "bg-amber"
                  : "bg-accent"
              }`}
            />
            <span
              className={`relative inline-flex h-2 w-2 rounded-full ${
                risk === "critical"
                  ? "bg-red"
                  : risk === "warning"
                  ? "bg-amber"
                  : "bg-accent"
              }`}
            />
          </span>
          <h2 className="font-mono text-2xs uppercase tracking-[0.3em] text-mute2">
            bifrost core
          </h2>
          <span className={`font-mono text-2xs uppercase tracking-wider ${riskTone}`}>
            · {risk}
          </span>
        </div>
        <div className="font-mono text-2xs uppercase tracking-wider text-muted">
          {running ? <span className="text-accent">link: active</span> : "link: idle"}
        </div>
      </div>

      <div className="relative flex flex-1 items-center justify-center overflow-hidden px-4 py-6 grid-bg">
        {/* animated concentric rings */}
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div
            className="animate-core-ring rounded-full border border-dashed opacity-30"
            style={{
              width: 340,
              height: 340,
              borderColor: ringColor,
            }}
          />
        </div>
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div
            className="rounded-full border opacity-25"
            style={{
              width: 260,
              height: 260,
              borderColor: ringColor,
            }}
          />
        </div>

        {/* core orb */}
        <div
          className="relative flex h-40 w-40 items-center justify-center rounded-full animate-core-pulse"
          style={{
            background:
              "radial-gradient(circle at 50% 45%, rgba(34,211,238,0.35), rgba(13,20,32,0.9) 65%, rgba(4,7,12,1) 100%)",
            border: "1px solid rgba(34,211,238,0.35)",
          }}
        >
          <div className="flex flex-col items-center">
            <div className="font-mono text-2xs uppercase tracking-[0.3em] text-accent/80">
              system
            </div>
            <div className="mt-0.5 font-mono text-2xl tabular-nums text-inkhi text-accent-glow">
              {activeActions}
            </div>
            <div className="font-mono text-2xs uppercase tracking-wider text-mute2">
              actions
            </div>
          </div>
        </div>

        {/* radial stats */}
        <div className="pointer-events-auto absolute left-3 top-3 flex flex-col gap-1">
          <CoreStat label="programs" value={activePrograms} />
          <CoreStat
            label="capital"
            value={m?.capital_active ?? 0}
            sub={`${m?.capital_overdue ?? 0} od`}
            tone={m?.capital_overdue ? "red" : undefined}
          />
        </div>
        <div className="pointer-events-auto absolute right-3 top-3 flex flex-col items-end gap-1">
          <CoreStat
            label="approvals"
            value={m?.capital_pending_approvals ?? 0}
            tone={m?.capital_pending_approvals ? "amber" : undefined}
          />
          <CoreStat
            label="engine"
            value={m?.engine_writes_pending ?? 0}
            sub={`${m?.engine_writes_failed ?? 0} fail`}
            tone={m?.engine_writes_failed ? "red" : undefined}
          />
        </div>
        <div className="pointer-events-auto absolute left-3 bottom-3 flex flex-col gap-1">
          <CoreStat
            label="market"
            value={m?.market_accounts ?? 0}
            sub={`${m?.market_follow_ups_due ?? 0} due`}
            tone={m?.market_follow_ups_due ? "amber" : undefined}
          />
        </div>
        <div className="pointer-events-auto absolute right-3 bottom-3 flex flex-col items-end gap-1">
          <CoreStat
            label="suppliers"
            value={m?.suppliers_qualified ?? 0}
            sub={`${m?.suppliers_total ?? 0} tot`}
          />
          <CoreStat
            label="alerts"
            value={alerts?.total ?? 0}
            tone={
              (alerts?.counts_by_severity.critical ?? 0) > 0
                ? "red"
                : (alerts?.counts_by_severity.warn ?? 0) > 0
                ? "amber"
                : undefined
            }
          />
        </div>
      </div>

      <div className="grid grid-cols-3 border-t border-border/80 text-2xs font-mono uppercase tracking-wider">
        <CoreAction
          label="brief"
          onClick={() => runCommand("executive briefing")}
        />
        <CoreAction
          label="rank pipeline"
          onClick={() => runCommand("rank my pipeline")}
          divider
        />
        <CoreAction
          label="review approvals"
          onClick={() => runCommand("review approvals")}
          divider
        />
      </div>

      {briefing?.headline && (
        <div className="border-t border-border/80 px-3 py-1.5 text-2xs text-mute2 animate-fade-in">
          <span className="text-muted">briefing › </span>
          <span className="text-ink">{briefing.headline}</span>
        </div>
      )}
    </section>
  );
}

function CoreStat({
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
    <div className="glass border border-border2 px-2 py-1 backdrop-blur-md animate-fade-in">
      <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted">
        {label}
      </div>
      <div className={`font-mono text-md tabular-nums leading-tight ${color}`}>
        {value}
      </div>
      {sub && (
        <div className="font-mono text-[9px] uppercase tracking-wider text-muted">
          {sub}
        </div>
      )}
    </div>
  );
}

function CoreAction({
  label,
  onClick,
  divider,
}: {
  label: string;
  onClick: () => void;
  divider?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={`group px-3 py-2 text-muted transition-colors hover:bg-accent/5 hover:text-accent ${
        divider ? "border-l border-border/80" : ""
      }`}
    >
      <span className="text-accent/60 group-hover:text-accent">▸</span>{" "}
      <span>{label}</span>
    </button>
  );
}
