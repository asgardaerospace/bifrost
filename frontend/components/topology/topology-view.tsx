"use client";

/**
 * Topology view container — Sprint 7.
 *
 * Combines the spatial graph renderer with a propagation-path inspector
 * and cluster summary. Org-scope by default; can be filtered to a single
 * mission's neighborhood.
 */

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "@/lib/api";
import { Empty, Panel, Pill } from "@/components/ui";
import type { PropagationPath, TopologyView as TopologyData } from "@/types/api";
import { TopologyGraph } from "./topology-graph";
import { bandToneClass } from "@/components/horizon/atmosphere";

export function TopologyView({ missionId }: { missionId?: number }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["sprint7-topology", missionId ?? "org"],
    queryFn: () => api.topology({ mission_id: missionId }),
    refetchInterval: 60_000,
  });

  const [selectedPath, setSelectedPath] = useState<PropagationPath | null>(null);

  return (
    <div className="space-y-4 p-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="font-mono text-2xs uppercase tracking-[0.3em] text-accent/70">
            mission topology
          </div>
          <h1 className="mt-1 text-xl font-semibold text-inkhi">
            {missionId ? `Mission #${missionId} neighborhood` : "Strategic relationship surface"}
          </h1>
          <p className="mt-1 text-xs text-muted">
            Spatial cognition layer. Edges show pressure direction; pulses trace
            propagation paths to strain or critical missions.
          </p>
        </div>
        {data && (
          <div className="flex gap-2 font-mono text-2xs uppercase tracking-wider text-muted">
            <Pill tone="default">nodes {data.nodes.length}</Pill>
            <Pill tone="default">edges {data.edges.length}</Pill>
            <Pill tone="accent">paths {data.propagation_paths.length}</Pill>
          </div>
        )}
      </header>

      {error && (
        <Panel title="error">
          <Empty>Topology surface unavailable.</Empty>
        </Panel>
      )}
      {isLoading && (
        <Panel title="loading">
          <Empty>Tracing relationship graph…</Empty>
        </Panel>
      )}

      {data && (
        <>
          <Panel title={`graph · ${data.scope}`}>
            {data.nodes.length === 0 ? (
              <Empty>
                No relationships to render. Link missions to suppliers,
                programs, intel, or other missions to populate the topology.
              </Empty>
            ) : (
              <div className="overflow-hidden rounded-md border border-border bg-bgdeep/60">
                <TopologyGraph view={data} highlightedPath={selectedPath} />
              </div>
            )}
          </Panel>

          <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
            <Panel title={`propagation paths · ${data.propagation_paths.length}`}>
              {data.propagation_paths.length === 0 ? (
                <Empty>No active propagation paths to critical missions.</Empty>
              ) : (
                <div className="flex flex-col gap-2">
                  {data.propagation_paths.map((p) => {
                    const active = selectedPath?.path.join(">") === p.path.join(">");
                    return (
                      <button
                        key={p.path.join(">")}
                        type="button"
                        onClick={() => setSelectedPath(active ? null : p)}
                        className={
                          "rounded-md border px-3 py-2 text-left transition-colors " +
                          (active
                            ? "border-accent/50 bg-accent/10"
                            : "border-border/70 bg-panel/60 hover:bg-panel2")
                        }
                      >
                        <div className="flex items-center justify-between">
                          <span
                            className={
                              "font-mono text-2xs uppercase tracking-wider " +
                              bandToneClass(p.band)
                            }
                          >
                            ● {p.band} · intensity {p.intensity}
                          </span>
                          <span className="font-mono text-2xs text-muted">
                            depth {p.path.length - 1}
                          </span>
                        </div>
                        <div className="mt-1 truncate font-mono text-xs text-ink">
                          {p.path.join(" → ")}
                        </div>
                        <div className="mt-1 text-2xs text-muted">{p.explanation}</div>
                      </button>
                    );
                  })}
                </div>
              )}
            </Panel>

            <Panel title="cluster summary">
              {Object.keys(data.cluster_summary).length === 0 ? (
                <Empty>No clusters.</Empty>
              ) : (
                <ul className="flex flex-col gap-1 font-mono text-xs">
                  {Object.entries(data.cluster_summary)
                    .sort((a, b) => b[1] - a[1])
                    .map(([cluster, count]) => (
                      <li
                        key={cluster}
                        className="flex items-center justify-between border-b border-border/60 py-1"
                      >
                        <span className="text-muted">{cluster}</span>
                        <span className="tabular-nums text-ink">{count}</span>
                      </li>
                    ))}
                </ul>
              )}
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}
