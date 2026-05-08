"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

/**
 * Shows other operators currently viewing the same mission.
 *
 * Sprint 2 — read-only. Live cursors / collaborative editing are explicitly
 * out of scope. This is a presence indicator only.
 */
export function PresencePill({ missionId }: { missionId: number | null }) {
  const { data } = useQuery({
    queryKey: ["presence", missionId ?? "global"],
    queryFn: () =>
      missionId === null
        ? api.presenceActive()
        : api.presenceForMission(missionId),
    refetchInterval: 30_000,
    staleTime: 15_000,
  });

  const operators = data?.operators ?? [];
  if (operators.length === 0) {
    return (
      <span
        className="font-mono text-2xs uppercase tracking-wider text-mute2"
        title="No other operators on this mission"
      >
        ◇ solo
      </span>
    );
  }
  const visible = operators.slice(0, 3);
  const overflow = operators.length - visible.length;
  return (
    <span
      className="flex items-center gap-1 font-mono text-2xs uppercase tracking-wider text-mute2"
      title={operators
        .map((o) => o.display_name ?? `#${o.client_id.slice(0, 6)}`)
        .join("\n")}
    >
      <span className="text-accent/80">◈</span>
      {visible.map((o) => (
        <span
          key={o.client_id}
          className="rounded-md border border-border/60 bg-panel2/60 px-1.5 py-0.5 text-accent/80"
        >
          {(o.display_name ?? "op").slice(0, 12)}
        </span>
      ))}
      {overflow > 0 && (
        <span className="text-mute2">+{overflow}</span>
      )}
    </span>
  );
}
