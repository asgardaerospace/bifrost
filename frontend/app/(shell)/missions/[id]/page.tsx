"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { CognitionPanel } from "@/components/shell/cognition-panel";
import { TopologyView } from "@/components/topology/topology-view";
import { OperationalTimelineView } from "@/components/timeline/operational-timeline";
import { MemoryPanel } from "@/components/shell/memory-panel";
import { MissionDetailTabs, MissionTabPanel, type MissionTabKey } from "@/components/shell/mission-detail-tabs";
import { MissionIntelligence } from "@/components/shell/mission-intelligence";
import { MissionLinkDialog } from "@/components/shell/mission-link-dialog";
import { RecommendationsPanel } from "@/components/shell/recommendations-panel";
import { RelatedMissions } from "@/components/shell/related-missions";
import { SimulationPanel } from "@/components/shell/simulation-panel";
import { SynthesisCard } from "@/components/shell/synthesis-card";
import { useShell } from "@/components/shell/shell-context";
import { api } from "@/lib/api";
import type {
  ExecutionQueueItemRead,
  MissionEntityRead,
  MissionHealth,
} from "@/types/api";

const HEALTH_TONE: Record<MissionHealth, string> = {
  nominal: "text-green",
  watch: "text-amber",
  strain: "text-amber",
  critical: "text-red",
};

const ENTITY_TYPE_LABEL: Record<string, string> = {
  investor_firm: "Investor firms",
  investor_opportunity: "Investor opportunities",
  account: "Accounts",
  market_opportunity: "Market opportunities",
  program: "Programs",
  supplier: "Suppliers",
  intel_item: "Intel signals",
  communication: "Communications",
  task: "Tasks",
};

function pressureBar(score: number) {
  const pct = Math.max(0, Math.min(100, score));
  const tone =
    pct >= 80
      ? "from-red/60 to-red"
      : pct >= 60
      ? "from-amber/60 to-amber"
      : pct >= 35
      ? "from-cyan/40 to-accent"
      : "from-accent/30 to-teal/60";
  return (
    <div className="relative h-2 w-full overflow-hidden rounded-full bg-panel3/60">
      <div
        className={`absolute inset-y-0 left-0 bg-gradient-to-r ${tone}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export default function MissionDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const { setSelectedMissionId } = useShell();
  const qc = useQueryClient();
  const [tab, setTab] = useState<
    "overview" | "entities" | "timeline" | "queue" | "dependencies" | "memory" | "topology" | "replay"
  >("overview");
  const [linkDialogOpen, setLinkDialogOpen] = useState(false);

  // Tell the shell which mission is in focus so the tactical rail filters by it.
  useEffect(() => {
    if (!Number.isNaN(id)) {
      setSelectedMissionId(id);
      return () => setSelectedMissionId(null);
    }
  }, [id, setSelectedMissionId]);

  const { data: mission, isLoading } = useQuery({
    queryKey: ["mission", id],
    queryFn: () => api.getMission(id),
    enabled: !Number.isNaN(id),
  });
  const { data: pressure } = useQuery({
    queryKey: ["mission", id, "pressure"],
    queryFn: () => api.missionPressure(id),
    enabled: !Number.isNaN(id),
  });
  const { data: deps } = useQuery({
    queryKey: ["mission", id, "deps"],
    queryFn: () => api.missionDependencies(id),
    enabled: !Number.isNaN(id),
  });
  const { data: timeline } = useQuery({
    queryKey: ["mission", id, "timeline"],
    queryFn: () => api.missionTimeline(id, 100),
    enabled: !Number.isNaN(id),
  });
  const { data: grouped } = useQuery({
    queryKey: ["mission", id, "entities-grouped"],
    queryFn: () => api.missionEntitiesGrouped(id),
    enabled: !Number.isNaN(id),
  });
  const { data: missionQueue } = useQuery({
    queryKey: ["mission", id, "queue"],
    queryFn: () => api.executionQueue({ mission_id: id, limit: 100 }),
    enabled: !Number.isNaN(id),
  });

  const totalEntities = grouped
    ? Object.values(grouped).reduce((acc, arr) => acc + arr.length, 0)
    : 0;
  const totalDeps = (deps?.upstream.length ?? 0) + (deps?.downstream.length ?? 0);

  if (Number.isNaN(id)) {
    return <div className="p-6 font-mono text-xs text-red">invalid mission id</div>;
  }
  if (isLoading || !mission) {
    return (
      <div className="p-6 font-mono text-xs text-mute2 animate-soft-pulse">
        ▸ syncing mission…
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <div className="flex items-center gap-2 font-mono text-2xs uppercase tracking-wider text-mute2">
        <Link href="/missions" className="hover:text-accent">
          ◂ missions
        </Link>
        <span>/</span>
        <span className="text-accent">{mission.codename}</span>
      </div>

      <header className="flex items-end justify-between">
        <div>
          <div className="flex items-center gap-3">
            <span className="font-mono text-2xs uppercase tracking-[0.3em] text-accent/80">
              {mission.codename}
            </span>
            <span className={`font-mono text-2xs uppercase tracking-wider ${HEALTH_TONE[mission.health_status]}`}>
              ● {mission.health_status}
            </span>
            <span className="chip">{mission.status}</span>
            <span className="chip">{mission.priority}</span>
          </div>
          <h1 className="mt-2 text-2xl font-semibold text-inkhi text-accent-glow">
            {mission.name}
          </h1>
          {mission.description && (
            <p className="mt-1 max-w-3xl text-sm text-mute2">{mission.description}</p>
          )}
        </div>
        <button
          type="button"
          onClick={() => setLinkDialogOpen(true)}
          className="chip-accent rounded-md px-3 py-2 text-xs font-semibold uppercase tracking-widest hover:bg-accent/30"
        >
          + link entity
        </button>
      </header>

      <MissionDetailTabs
        active={tab as MissionTabKey}
        onChange={(t) => setTab(t as typeof tab)}
        tabs={[
          { key: "overview", label: "Overview" },
          { key: "entities", label: "Linked", badge: totalEntities },
          { key: "timeline", label: "Timeline", badge: timeline?.count ?? 0 },
          { key: "queue", label: "Queue", badge: missionQueue?.count ?? 0 },
          { key: "dependencies", label: "Deps", badge: totalDeps },
          { key: "memory" as MissionTabKey, label: "Memory" },
          { key: "topology" as MissionTabKey, label: "Topology" },
          { key: "replay" as MissionTabKey, label: "Replay" },
        ]}
      />

      {tab === "overview" && (
        <MissionTabPanel>
          <SynthesisCard missionId={id} />

          <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <RecommendationsPanel missionId={id} />
            <SimulationPanel missionId={id} />
          </div>

          <section className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
            <div className="rounded-lg border border-border/60 bg-panel/60 p-4">
              <div className="font-mono text-2xs uppercase tracking-widest text-mute2">
                pressure
              </div>
              <div className="mt-2 flex items-baseline gap-3">
                <span className="text-3xl font-semibold text-inkhi">
                  {pressure?.pressure_score ?? mission.pressure_score}
                </span>
                <span className="font-mono text-2xs uppercase tracking-wider text-mute2">
                  /100
                </span>
              </div>
              <div className="mt-2">
                {pressureBar(pressure?.pressure_score ?? mission.pressure_score)}
              </div>
              {pressure && (
                <ul className="mt-3 space-y-1 font-mono text-2xs text-mute2">
                  {Object.entries(pressure.components)
                    .filter(([, v]) => typeof v === "number")
                    .map(([k, v]) => (
                      <li key={k} className="flex justify-between">
                        <span>{k}</span>
                        <span>{(v as number) >= 0 ? `+${v}` : `${v}`}</span>
                      </li>
                    ))}
                </ul>
              )}
            </div>

            <div className="rounded-lg border border-border/60 bg-panel/60 p-4">
              <div className="font-mono text-2xs uppercase tracking-widest text-mute2">
                posture
              </div>
              <ul className="mt-2 space-y-2 text-xs text-ink">
                <li className="flex items-center justify-between">
                  <span className="text-mute2">blockers</span>
                  <span className="font-semibold">
                    {pressure?.blockers_count ?? 0}
                  </span>
                </li>
                <li className="flex items-center justify-between">
                  <span className="text-mute2">overdue</span>
                  <span className="font-semibold">
                    {pressure?.overdue_count ?? 0}
                  </span>
                </li>
                <li className="flex items-center justify-between">
                  <span className="text-mute2">pending approvals</span>
                  <span className="font-semibold">
                    {pressure?.pending_approvals_count ?? 0}
                  </span>
                </li>
                <li className="flex items-center justify-between">
                  <span className="text-mute2">linked entities</span>
                  <span className="font-semibold">{totalEntities}</span>
                </li>
                <li className="flex items-center justify-between">
                  <span className="text-mute2">queue items</span>
                  <span className="font-semibold">
                    {missionQueue?.count ?? 0}
                  </span>
                </li>
              </ul>
            </div>

            <div className="rounded-lg border border-border/60 bg-panel/60 p-4">
              <div className="font-mono text-2xs uppercase tracking-widest text-mute2">
                lifecycle
              </div>
              <ul className="mt-2 space-y-2 text-xs">
                <li>
                  <span className="text-mute2">starts</span>
                  <div className="text-ink">
                    {mission.starts_at
                      ? new Date(mission.starts_at).toLocaleString()
                      : "—"}
                  </div>
                </li>
                <li>
                  <span className="text-mute2">target completion</span>
                  <div className="text-ink">
                    {mission.target_completion_at
                      ? new Date(mission.target_completion_at).toLocaleString()
                      : "—"}
                  </div>
                </li>
                <li>
                  <span className="text-mute2">created</span>
                  <div className="text-ink">
                    {new Date(mission.created_at).toLocaleString()}
                  </div>
                </li>
              </ul>
            </div>
          </section>
        </MissionTabPanel>
      )}

      {tab === "entities" && (
        <MissionTabPanel>
          {totalEntities === 0 ? (
            <div className="rounded-lg border border-border/60 bg-panel/40 p-8 text-center">
              <div className="font-mono text-2xs uppercase tracking-widest text-accent/70">
                ▸ no linked entities
              </div>
              <div className="mt-2 text-sm text-mute2">
                Click <em>+ link entity</em> to attach an investor, program,
                supplier, market opportunity, or intel signal to this mission.
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {Object.entries(grouped ?? {}).map(([etype, rows]) => (
                <EntityGroup
                  key={etype}
                  entityType={etype}
                  rows={rows}
                  onUnlink={async (linkId) => {
                    await api.unlinkMissionEntity(id, linkId);
                    qc.invalidateQueries({
                      queryKey: ["mission", id, "entities-grouped"],
                    });
                    qc.invalidateQueries({
                      queryKey: ["mission", id, "timeline"],
                    });
                  }}
                />
              ))}
            </div>
          )}
        </MissionTabPanel>
      )}

      {tab === "timeline" && (
        <MissionTabPanel>
          <div className="rounded-lg border border-border/60 bg-panel/60">
            <header className="flex items-center justify-between border-b border-border/60 px-4 py-3">
              <span className="font-mono text-2xs uppercase tracking-widest text-accent/80">
                ▸ timeline
              </span>
              <span className="font-mono text-2xs text-mute2">
                {timeline?.count ?? 0} items
              </span>
            </header>
            <ul className="divide-y divide-border/60">
              {(timeline?.items ?? []).map((it) => (
                <li
                  key={`${it.item_type}-${it.item_id}`}
                  className="px-4 py-3 hover:bg-panel2/40"
                >
                  <div className="flex items-center justify-between font-mono text-2xs uppercase tracking-wider text-mute2">
                    <span className="text-accent/80">{it.item_type}</span>
                    <span>{new Date(it.occurred_at).toLocaleString()}</span>
                  </div>
                  <div className="mt-1 text-sm text-ink">{it.title}</div>
                  {it.summary && (
                    <div className="mt-1 line-clamp-2 text-xs text-mute2">
                      {it.summary}
                    </div>
                  )}
                </li>
              ))}
              {(timeline?.count ?? 0) === 0 && (
                <li className="px-4 py-8 text-center font-mono text-2xs text-mute2">
                  timeline empty — no linked activity yet
                </li>
              )}
            </ul>
          </div>
        </MissionTabPanel>
      )}

      {tab === "queue" && (
        <MissionTabPanel>
          <MissionQueue items={missionQueue?.items ?? []} missionId={id} />
        </MissionTabPanel>
      )}

      {tab === "dependencies" && (
        <MissionTabPanel>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <DependencyList
              title="upstream"
              edges={deps?.upstream ?? []}
            />
            <DependencyList
              title="downstream"
              edges={deps?.downstream ?? []}
            />
          </div>
        </MissionTabPanel>
      )}

      {tab === "memory" && (
        <MissionTabPanel>
          <div className="space-y-4">
            <CognitionPanel missionId={id} />
            <MissionIntelligence missionId={id} />
            <MemoryPanel missionId={id} />
            <RelatedMissions missionId={id} />
          </div>
        </MissionTabPanel>
      )}

      {tab === "topology" && (
        <MissionTabPanel>
          <TopologyView missionId={id} />
        </MissionTabPanel>
      )}

      {tab === "replay" && (
        <MissionTabPanel>
          <OperationalTimelineView missionId={id} />
        </MissionTabPanel>
      )}

      <MissionLinkDialog
        missionId={id}
        open={linkDialogOpen}
        onClose={() => setLinkDialogOpen(false)}
      />
    </div>
  );
}

function EntityGroup({
  entityType,
  rows,
  onUnlink,
}: {
  entityType: string;
  rows: MissionEntityRead[];
  onUnlink: (linkId: number) => void;
}) {
  return (
    <section className="rounded-lg border border-border/60 bg-panel/60">
      <header className="flex items-center justify-between border-b border-border/60 px-3 py-2">
        <span className="font-mono text-2xs uppercase tracking-widest text-accent/80">
          {ENTITY_TYPE_LABEL[entityType] ?? entityType}
        </span>
        <span className="font-mono text-2xs text-mute2">{rows.length}</span>
      </header>
      <ul className="divide-y divide-border/60">
        {rows.map((r) => (
          <li
            key={r.id}
            className="flex items-start justify-between gap-3 px-3 py-2"
          >
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-mono text-2xs uppercase tracking-wider text-accent/80">
                  {r.relationship_type}
                </span>
                <span className="text-sm text-ink">#{r.entity_id}</span>
              </div>
              {r.notes && (
                <div className="mt-1 line-clamp-2 text-xs text-mute2">
                  {r.notes}
                </div>
              )}
            </div>
            <button
              onClick={() => onUnlink(r.id)}
              className="font-mono text-2xs uppercase tracking-wider text-mute2 hover:text-red"
              type="button"
            >
              unlink
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function DependencyList({
  title,
  edges,
}: {
  title: string;
  edges: { relationship_type: string; other_mission_id: number; other_codename?: string | null; other_name?: string | null }[];
}) {
  return (
    <section className="rounded-lg border border-border/60 bg-panel/60">
      <header className="border-b border-border/60 px-3 py-2 font-mono text-2xs uppercase tracking-widest text-accent/80">
        {title}
      </header>
      <ul className="divide-y divide-border/60">
        {edges.map((e, i) => (
          <li key={`${title}-${i}`} className="px-3 py-2">
            <div className="flex items-center gap-2">
              <span className="font-mono text-2xs uppercase tracking-wider text-accent/80">
                {e.relationship_type}
              </span>
              <Link
                href={`/missions/${e.other_mission_id}`}
                className="text-sm text-ink hover:text-accent"
              >
                {e.other_codename ?? `#${e.other_mission_id}`}
              </Link>
            </div>
            {e.other_name && (
              <div className="mt-0.5 text-xs text-mute2">{e.other_name}</div>
            )}
          </li>
        ))}
        {edges.length === 0 && (
          <li className="px-3 py-6 text-center font-mono text-2xs text-mute2">
            none
          </li>
        )}
      </ul>
    </section>
  );
}

function MissionQueue({
  items,
  missionId,
}: {
  items: ExecutionQueueItemRead[];
  missionId: number;
}) {
  const qc = useQueryClient();
  const decide = useMutation({
    mutationFn: ({
      itemId,
      decision,
    }: {
      itemId: number;
      decision: "approved" | "rejected";
    }) => api.decideQueueItemApproval(itemId, decision),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mission", missionId, "queue"] });
      qc.invalidateQueries({ queryKey: ["execution"] });
    },
  });

  if (items.length === 0) {
    return (
      <div className="rounded-lg border border-border/60 bg-panel/40 p-8 text-center font-mono text-2xs uppercase tracking-widest text-accent/70">
        ▸ queue clear for this mission
      </div>
    );
  }

  return (
    <ul className="flex flex-col gap-2">
      {items.map((it, i) => (
        <li
          key={`${it.id ?? "p"}-${i}`}
          className="rounded-md border border-border/60 bg-panel/60 p-3"
        >
          <div className="flex items-center justify-between font-mono text-2xs uppercase tracking-wider text-mute2">
            <span className="text-accent/80">{it.item_type}</span>
            <div className="flex items-center gap-3">
              <span>priority {it.priority_score}</span>
              <span>{it.status}</span>
              {it.requires_approval && (
                <span className="text-amber">approval-gated</span>
              )}
            </div>
          </div>
          <div className="mt-1 text-sm text-ink">{it.title}</div>
          {it.summary && (
            <div className="mt-1 line-clamp-2 text-xs text-mute2">{it.summary}</div>
          )}
          <div className="mt-2 flex items-center gap-2 font-mono text-2xs text-mute2">
            {it.owner && <span>@{it.owner}</span>}
            {it.due_at && (
              <span>due {new Date(it.due_at).toLocaleString()}</span>
            )}
            {it.source_type && !it.is_projected && (
              <span className="ml-auto">source: {it.source_type}</span>
            )}
            {it.is_projected && <span className="ml-auto chip">projected</span>}
          </div>
          {it.requires_approval && it.status === "queued" && it.id !== null && it.id !== undefined && (
            <div className="mt-3 flex items-center gap-2 border-t border-border/60 pt-2">
              <button
                type="button"
                onClick={() =>
                  decide.mutate({ itemId: it.id!, decision: "approved" })
                }
                className="rounded-md border border-green/40 bg-green/10 px-3 py-1 font-mono text-2xs uppercase tracking-widest text-green hover:bg-green/20"
              >
                approve
              </button>
              <button
                type="button"
                onClick={() =>
                  decide.mutate({ itemId: it.id!, decision: "rejected" })
                }
                className="rounded-md border border-red/40 bg-red/10 px-3 py-1 font-mono text-2xs uppercase tracking-widest text-red hover:bg-red/20"
              >
                reject
              </button>
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}
