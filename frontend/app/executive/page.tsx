"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import { Empty, Panel, Pill } from "@/components/ui";
import {
  ActionQueueView,
  AlertListView,
  BriefingView,
} from "@/components/executive";

type Tab = "briefing" | "queue" | "alerts";

const DOMAINS = [
  "all",
  "capital",
  "market",
  "program",
  "supplier",
  "approval",
  "engine",
] as const;

export default function ExecutivePage() {
  const [tab, setTab] = useState<Tab>("briefing");
  const [domain, setDomain] = useState<(typeof DOMAINS)[number]>("all");
  const [severity, setSeverity] = useState<"all" | "critical" | "warn" | "info">(
    "all",
  );

  const briefing = useQuery({
    queryKey: ["exec-briefing"],
    queryFn: api.executiveBriefing,
    enabled: tab === "briefing",
  });
  const queue = useQuery({
    queryKey: ["exec-queue", domain],
    queryFn: () =>
      api.executiveActionQueue({
        domain: domain === "all" ? undefined : domain,
        limit: 100,
      }),
    enabled: tab === "queue",
  });
  const alerts = useQuery({
    queryKey: ["exec-alerts", severity],
    queryFn: () =>
      api.executiveAlerts(severity === "all" ? undefined : severity),
    enabled: tab === "alerts",
  });

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">Executive</h1>
        <p className="mt-1 text-sm text-muted">
          Daily briefing, unified action queue, and cross-domain alerts.
        </p>
      </header>

      <div className="flex items-center gap-2">
        {(["briefing", "queue", "alerts"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={
              "rounded border px-3 py-1 font-mono text-[11px] uppercase tracking-widest " +
              (tab === t
                ? "border-accent text-accent"
                : "border-border text-muted hover:text-ink")
            }
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "briefing" &&
        (briefing.isLoading ? (
          <Empty>Generating briefing…</Empty>
        ) : !briefing.data ? (
          <Empty>No briefing available.</Empty>
        ) : (
          <BriefingView briefing={briefing.data} />
        ))}

      {tab === "queue" && (
        <>
          <div className="flex flex-wrap gap-2">
            {DOMAINS.map((d) => (
              <button
                key={d}
                onClick={() => setDomain(d)}
                className={
                  "rounded border px-2 py-1 font-mono text-[11px] uppercase tracking-widest " +
                  (domain === d
                    ? "border-accent text-accent"
                    : "border-border text-muted hover:text-ink")
                }
              >
                {d}
              </button>
            ))}
          </div>
          <Panel
            title="Action queue"
            right={
              queue.data ? (
                <Pill tone="default">{queue.data.total} total</Pill>
              ) : null
            }
          >
            {queue.isLoading ? (
              <Empty>Loading…</Empty>
            ) : !queue.data ? (
              <Empty>No actions.</Empty>
            ) : (
              <ActionQueueView queue={queue.data} />
            )}
          </Panel>
        </>
      )}

      {tab === "alerts" && (
        <>
          <div className="flex items-center gap-2">
            {(["all", "critical", "warn", "info"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setSeverity(s)}
                className={
                  "rounded border px-2 py-1 font-mono text-[11px] uppercase tracking-widest " +
                  (severity === s
                    ? "border-accent text-accent"
                    : "border-border text-muted hover:text-ink")
                }
              >
                {s}
              </button>
            ))}
          </div>
          <Panel
            title="Alerts"
            right={
              alerts.data ? (
                <Pill tone="default">{alerts.data.total} total</Pill>
              ) : null
            }
          >
            {alerts.isLoading ? (
              <Empty>Loading…</Empty>
            ) : !alerts.data ? (
              <Empty>No alerts.</Empty>
            ) : (
              <AlertListView bundle={alerts.data} />
            )}
          </Panel>
        </>
      )}
    </div>
  );
}
