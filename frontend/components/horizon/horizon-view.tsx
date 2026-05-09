"use client";

/**
 * Executive Horizon view — Sprint 7.
 *
 * The strategic awareness surface. Calm, compressed, mission-centric.
 * Aggregates pressure-map / tempo / top missions / escalations /
 * opportunities into a single read.
 */

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { api } from "@/lib/api";
import { Empty, Panel, Pill } from "@/components/ui";
import type {
  HorizonEscalation,
  HorizonMissionPulse,
  HorizonOpportunity,
  HorizonPressureMap,
  HorizonTempo,
  HorizonView as HorizonData,
} from "@/types/api";
import { bandFillClass, bandLabel, bandToneClass } from "./atmosphere";
import { AgentPresence } from "./agent-presence";

function PressureBars({ map }: { map: HorizonPressureMap }) {
  const total = Math.max(
    1,
    map.nominal + map.watch + map.strain + map.critical,
  );
  const pct = (n: number) => `${(n / total) * 100}%`;
  return (
    <div className="flex flex-col gap-2">
      <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-panel3/60 ring-1 ring-border">
        <div
          className="bg-bandnominal/70"
          style={{ width: pct(map.nominal) }}
          title={`nominal ${map.nominal}`}
        />
        <div
          className="bg-bandwatch/70"
          style={{ width: pct(map.watch) }}
          title={`watch ${map.watch}`}
        />
        <div
          className="bg-bandstrain/80"
          style={{ width: pct(map.strain) }}
          title={`strain ${map.strain}`}
        />
        <div
          className="bg-bandcritical/80"
          style={{ width: pct(map.critical) }}
          title={`critical ${map.critical}`}
        />
      </div>
      <div className="grid grid-cols-4 gap-2 font-mono text-2xs uppercase tracking-wider">
        <div className="text-bandnominal">● nominal {map.nominal}</div>
        <div className="text-bandwatch">● watch {map.watch}</div>
        <div className="text-bandstrain">● strain {map.strain}</div>
        <div className="text-bandcritical">● critical {map.critical}</div>
      </div>
      <div className="flex items-center justify-between text-xs text-muted">
        <span>
          avg{" "}
          <span className="tabular-nums text-ink">{map.average_score}</span>
        </span>
        {map.peak_mission_codename ? (
          <span>
            peak{" "}
            <span className="tabular-nums text-ink">{map.peak_score}</span>{" "}
            <span className="text-accent">{map.peak_mission_codename}</span>
          </span>
        ) : (
          <span>peak {map.peak_score}</span>
        )}
      </div>
    </div>
  );
}

function TempoStrip({ tempo }: { tempo: HorizonTempo }) {
  const cells = [
    ["events / hr", tempo.events_last_hour],
    ["events / 24h", tempo.events_last_24h],
    ["approvals / 24h", tempo.approvals_decided_24h],
    ["proposed / 24h", tempo.proposed_actions_decided_24h],
    ["agent runs / 24h", tempo.agent_runs_24h],
    ["workflows / 24h", tempo.workflows_completed_24h],
  ] as const;
  return (
    <div className="grid grid-cols-3 gap-2 md:grid-cols-6">
      {cells.map(([label, value]) => (
        <div
          key={label}
          className="rounded-md border border-border bg-panel2/60 px-3 py-2"
        >
          <div className="font-mono text-2xs uppercase tracking-wider text-muted">
            {label}
          </div>
          <div className="mt-1 text-lg font-semibold tabular-nums">{value}</div>
        </div>
      ))}
    </div>
  );
}

function MissionPulseRow({ m }: { m: HorizonMissionPulse }) {
  const delta = m.pressure_delta_24h;
  const arrow = delta > 0 ? "↑" : delta < 0 ? "↓" : "·";
  const deltaTone =
    delta >= 5
      ? "text-bandcritical"
      : delta <= -5
      ? "text-bandnominal"
      : "text-muted";
  return (
    <Link
      href={`/missions/${m.mission_id}`}
      className="grid grid-cols-12 items-center gap-2 rounded-md border border-border/70 bg-panel/60 px-3 py-2 transition-colors hover:bg-panel2"
    >
      <div className="col-span-3 truncate">
        <div className="font-mono text-2xs uppercase tracking-wider text-accent/80">
          {m.codename}
        </div>
        <div className="truncate text-sm">{m.name}</div>
      </div>
      <div className="col-span-2 flex items-center gap-2">
        <span className={"font-mono text-2xs uppercase " + bandToneClass(m.health_status)}>
          ● {bandLabel(m.health_status)}
        </span>
      </div>
      <div className="col-span-2 flex items-center gap-2 tabular-nums">
        <span className="text-base font-semibold">{m.pressure_score}</span>
        <span className={"font-mono text-xs " + deltaTone}>
          {arrow}
          {delta !== 0 ? Math.abs(delta) : ""}
        </span>
      </div>
      <div className="col-span-5 flex flex-wrap items-center gap-1 text-2xs">
        {m.blockers > 0 && <Pill tone="danger">blockers {m.blockers}</Pill>}
        {m.overdue > 0 && <Pill tone="warn">overdue {m.overdue}</Pill>}
        {m.pending_approvals > 0 && (
          <Pill tone="warn">approvals {m.pending_approvals}</Pill>
        )}
        {m.open_proposed_actions > 0 && (
          <Pill tone="accent">proposed {m.open_proposed_actions}</Pill>
        )}
        {m.priority === "critical" && <Pill tone="danger">priority</Pill>}
      </div>
    </Link>
  );
}

function EscalationRow({ e }: { e: HorizonEscalation }) {
  const sev =
    e.severity === "critical"
      ? "danger"
      : e.severity === "warn"
      ? "warn"
      : "default";
  return (
    <div className="rounded-md border border-border/70 bg-panel/60 px-3 py-2">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Pill tone={sev}>{e.severity}</Pill>
          <span className="font-mono text-2xs uppercase tracking-wider text-muted">
            {e.domain}
          </span>
          {e.mission_codename && (
            <span className="font-mono text-2xs uppercase tracking-wider text-accent/80">
              {e.mission_codename}
            </span>
          )}
        </div>
        {e.link_hint && (
          <Link href={e.link_hint} className="text-2xs text-accent hover:underline">
            inspect →
          </Link>
        )}
      </div>
      <div className="mt-1 text-sm">{e.title}</div>
      <div className="mt-0.5 text-xs text-muted">{e.detail}</div>
    </div>
  );
}

function OpportunityRow({ o }: { o: HorizonOpportunity }) {
  return (
    <div className="rounded-md border border-border/70 bg-panel/60 px-3 py-2">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Pill tone="accent">{o.confidence}</Pill>
          <span className="font-mono text-2xs uppercase tracking-wider text-muted">
            {o.domain}
          </span>
        </div>
        {o.link_hint && (
          <Link href={o.link_hint} className="text-2xs text-accent hover:underline">
            inspect →
          </Link>
        )}
      </div>
      <div className="mt-1 text-sm">{o.title}</div>
      <div className="mt-0.5 text-xs text-muted">{o.detail}</div>
    </div>
  );
}

export function HorizonView() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["sprint7-horizon"],
    queryFn: () => api.horizon(8),
    refetchInterval: 30_000,
  });

  return (
    <div className="space-y-4 p-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="font-mono text-2xs uppercase tracking-[0.3em] text-accent/70">
            executive horizon
          </div>
          <h1 className="mt-1 text-xl font-semibold text-inkhi">
            Strategic awareness
          </h1>
          {data && (
            <p className="mt-1 text-xs text-muted">{data.headline}</p>
          )}
        </div>
        {data && (
          <div
            className={
              "rounded-md border border-border px-3 py-2 font-mono text-2xs uppercase tracking-wider " +
              bandFillClass(data.band) +
              " " +
              bandToneClass(data.band)
            }
          >
            band · {bandLabel(data.band)}
          </div>
        )}
      </header>

      {error && (
        <Panel title="error">
          <Empty>Unable to load horizon view.</Empty>
        </Panel>
      )}
      {isLoading && (
        <Panel title="loading">
          <Empty>Synchronizing strategic surfaces…</Empty>
        </Panel>
      )}

      {data && (
        <>
          <Panel title="organization pressure map">
            <PressureBars map={data.pressure_map} />
          </Panel>

          <Panel title="operational tempo">
            <TempoStrip tempo={data.tempo} />
          </Panel>

          {data.narrative.length > 0 && (
            <Panel title="narrative">
              <ul className="space-y-1 text-sm text-ink">
                {data.narrative.map((n, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-muted">›</span>
                    <span>{n}</span>
                  </li>
                ))}
              </ul>
            </Panel>
          )}

          <Panel title={`top missions · ${data.top_missions.length}`}>
            <div className="flex flex-col gap-2">
              {data.top_missions.length === 0 ? (
                <Empty>No active missions.</Empty>
              ) : (
                data.top_missions.map((m) => (
                  <MissionPulseRow key={m.mission_id} m={m} />
                ))
              )}
            </div>
          </Panel>

          <AgentPresence />

          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title={`escalations · ${data.escalations.length}`}>
              <div className="flex flex-col gap-2">
                {data.escalations.length === 0 ? (
                  <Empty>No active escalations.</Empty>
                ) : (
                  data.escalations.map((e) => <EscalationRow key={e.id} e={e} />)
                )}
              </div>
            </Panel>
            <Panel title={`opportunities · ${data.opportunities.length}`}>
              <div className="flex flex-col gap-2">
                {data.opportunities.length === 0 ? (
                  <Empty>No emerging opportunities.</Empty>
                ) : (
                  data.opportunities.map((o) => <OpportunityRow key={o.id} o={o} />)
                )}
              </div>
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}
