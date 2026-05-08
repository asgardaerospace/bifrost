"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { MissionRead, MissionHealth } from "@/types/api";

const HEALTH_TONE: Record<MissionHealth, string> = {
  nominal: "text-green",
  watch: "text-amber",
  strain: "text-amber",
  critical: "text-red",
};

const PRIORITY_TONE: Record<string, string> = {
  critical: "border-red/50 text-red",
  high: "border-amber/50 text-amber",
  normal: "border-border2 text-mute2",
  low: "border-border text-mute2",
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
    <div className="relative h-1 w-full overflow-hidden rounded-full bg-panel3/60">
      <div
        className={`absolute inset-y-0 left-0 bg-gradient-to-r ${tone}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function MissionCard({ mission }: { mission: MissionRead }) {
  return (
    <Link
      href={`/missions/${mission.id}`}
      className="group relative flex flex-col gap-3 rounded-lg border border-border/70 bg-panel/60 p-4 glass transition-colors hover:border-accent/60 hover:bg-panel2/70"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-2xs uppercase tracking-[0.3em] text-accent/80">
            {mission.codename}
          </span>
          <span className={`chip ${PRIORITY_TONE[mission.priority] ?? ""}`}>
            {mission.priority}
          </span>
        </div>
        <span className={`font-mono text-2xs uppercase tracking-wider ${HEALTH_TONE[mission.health_status]}`}>
          ● {mission.health_status}
        </span>
      </div>

      <div>
        <div className="text-base font-semibold text-inkhi group-hover:text-accent">
          {mission.name}
        </div>
        {mission.description && (
          <div className="mt-1 line-clamp-2 text-xs text-mute2">
            {mission.description}
          </div>
        )}
      </div>

      <div className="flex flex-col gap-1">
        <div className="flex items-center justify-between font-mono text-2xs uppercase tracking-wider text-mute2">
          <span>pressure {mission.pressure_score}</span>
          <span>{mission.status}</span>
        </div>
        {pressureBar(mission.pressure_score)}
      </div>
    </Link>
  );
}

export function MissionSurface() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["missions", "all"],
    queryFn: () => api.listMissions(),
    staleTime: 15_000,
  });

  return (
    <div className="flex flex-col gap-6 p-6">
      <header className="flex items-end justify-between">
        <div>
          <div className="font-mono text-2xs uppercase tracking-[0.3em] text-accent/80">
            ▸ mission cognition surface
          </div>
          <h1 className="mt-1 text-2xl font-semibold text-inkhi text-accent-glow">
            Mission Control
          </h1>
          <p className="mt-1 text-xs text-mute2">
            Operational missions organize the enterprise. Click any mission to
            inspect pressure, dependencies, timeline, and linked entities.
          </p>
        </div>
        <div className="flex items-center gap-3 font-mono text-2xs uppercase tracking-wider text-mute2">
          <span>{data?.length ?? 0} total</span>
          <Link
            href="/missions/new"
            className="chip-accent hover:bg-accent/30"
          >
            + new mission
          </Link>
        </div>
      </header>

      {isLoading && (
        <div className="rounded-lg border border-border/60 bg-panel/40 p-6 text-center font-mono text-xs text-mute2 animate-soft-pulse">
          ▸ syncing mission state…
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red/40 bg-red/10 p-4 font-mono text-xs text-red">
          mission service unreachable — check API base URL
        </div>
      )}

      {!isLoading && (data?.length ?? 0) === 0 && (
        <div className="rounded-lg border border-border/60 bg-panel/40 p-8 text-center">
          <div className="font-mono text-2xs uppercase tracking-widest text-accent/70">
            ▸ awaiting first mission
          </div>
          <div className="mt-2 text-sm text-mute2">
            No missions defined yet. Create one via{" "}
            <Link href="/missions/new" className="text-accent hover:underline">
              /missions/new
            </Link>{" "}
            or via <code className="font-mono text-xs">POST /api/v1/missions</code>.
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {(data ?? []).map((m) => (
          <MissionCard key={m.id} mission={m} />
        ))}
      </div>
    </div>
  );
}
