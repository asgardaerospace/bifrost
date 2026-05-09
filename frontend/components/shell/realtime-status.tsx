"use client";

import { useRealtimeStore } from "@/lib/realtime-store";

const TONES: Record<string, { dot: string; label: string }> = {
  idle: { dot: "bg-mute2/50", label: "idle" },
  connecting: { dot: "bg-amber animate-soft-pulse", label: "connecting" },
  open: { dot: "bg-green animate-soft-pulse", label: "live" },
  closed: { dot: "bg-red", label: "offline" },
};

function formatAge(ms: number): string {
  if (ms < 60_000) return `${Math.round(ms / 1000)}s ago`;
  if (ms < 3_600_000) return `${Math.round(ms / 60_000)}m ago`;
  return `${Math.round(ms / 3_600_000)}h ago`;
}

export function RealtimeStatus() {
  const status = useRealtimeStore((s) => s.status);
  const lastSyncAt = useRealtimeStore((s) => s.lastSyncAt);
  const reconnectCount = useRealtimeStore((s) => s.reconnectCount);
  const tone = TONES[status] ?? TONES.idle;
  const tooltipParts = [`Realtime ${tone.label}`];
  if (lastSyncAt) tooltipParts.push(`last sync ${formatAge(Date.now() - lastSyncAt)}`);
  if (reconnectCount > 0) tooltipParts.push(`${reconnectCount} reconnect${reconnectCount === 1 ? "" : "s"}`);

  return (
    <span
      className="flex items-center gap-1.5"
      title={tooltipParts.join(" · ")}
    >
      <span className="relative flex h-1.5 w-1.5">
        <span className={`absolute inline-flex h-full w-full rounded-full ${tone.dot}`} />
      </span>
      {tone.label}
    </span>
  );
}
