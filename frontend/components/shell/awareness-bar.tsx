"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { PresencePill } from "./presence-pill";
import { RealtimeStatus } from "./realtime-status";
import { useShell } from "./shell-context";

const HEALTH_TONE: Record<string, string> = {
  nominal: "text-green",
  watch: "text-amber",
  strain: "text-amber",
  critical: "text-red",
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

export function AwarenessBar() {
  const { selectedMissionId } = useShell();
  const { data: missions } = useQuery({
    queryKey: ["missions", "active"],
    queryFn: () => api.listMissions({ status: "active" }),
    staleTime: 15_000,
  });
  const { data: currentUser } = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => api.authMe(),
    staleTime: 60_000,
  });

  const total = missions?.length ?? 0;
  const critical = missions?.filter((m) => m.health_status === "critical").length ?? 0;
  const strain = missions?.filter((m) => m.health_status === "strain").length ?? 0;
  const watch = missions?.filter((m) => m.health_status === "watch").length ?? 0;
  const avg =
    missions && missions.length
      ? Math.round(
          missions.reduce((acc, m) => acc + (m.pressure_score ?? 0), 0) /
            missions.length,
        )
      : 0;

  return (
    <header className="relative flex h-14 shrink-0 items-center gap-6 border-b border-border/80 bg-panel/70 px-4 glass-strong hairline-accent">
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-accent/40 to-transparent" />

      <div className="flex items-baseline gap-2">
        <span className="font-mono text-2xs uppercase tracking-[0.3em] text-accent/70">
          asgard
        </span>
        <span className="relative font-semibold text-inkhi text-accent-glow">
          Bifrost
        </span>
        <span className="chip-accent">mission control</span>
      </div>

      <div className="ml-2 flex items-center gap-6 border-l border-border2 pl-6">
        <div className="flex flex-col gap-1">
          <span className="font-mono text-2xs uppercase tracking-wider text-mute2">
            active missions
          </span>
          <span className="text-sm font-semibold text-inkhi">{total}</span>
        </div>
        <div className="flex flex-col gap-1 min-w-[140px]">
          <span className="font-mono text-2xs uppercase tracking-wider text-mute2">
            org pressure {avg}
          </span>
          {pressureBar(avg)}
        </div>
        <div className="flex items-center gap-3 font-mono text-2xs uppercase tracking-wider">
          <span className={HEALTH_TONE.critical}>
            ● {critical} critical
          </span>
          <span className={HEALTH_TONE.strain}>
            ● {strain} strain
          </span>
          <span className={HEALTH_TONE.watch}>
            ● {watch} watch
          </span>
        </div>
      </div>

      <div className="ml-auto flex items-center gap-3 font-mono text-2xs uppercase tracking-wider text-mute2">
        {selectedMissionId !== null && (
          <span className="border-r border-border2 pr-3 text-accent/80">
            mission #{selectedMissionId}
          </span>
        )}
        <PresencePill missionId={selectedMissionId} />
        <span className="border-l border-border2 pl-3">
          <RealtimeStatus />
        </span>
        {currentUser && (
          <span
            className="border-l border-border2 pl-3"
            title={currentUser.email}
          >
            {currentUser.is_anonymous ? "anonymous" : currentUser.email}
            {" · "}
            <span className="text-accent/80">{currentUser.primary_role}</span>
          </span>
        )}
        <span className="border-l border-border2 pl-3">sprint 2</span>
      </div>
    </header>
  );
}
