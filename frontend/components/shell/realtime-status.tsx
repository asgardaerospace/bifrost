"use client";

import { useWsStatus } from "@/lib/realtime-store";

const TONES: Record<string, { dot: string; label: string }> = {
  idle: { dot: "bg-mute2/50", label: "idle" },
  connecting: { dot: "bg-amber animate-soft-pulse", label: "connecting" },
  open: { dot: "bg-green animate-soft-pulse", label: "live" },
  closed: { dot: "bg-red", label: "offline" },
};

export function RealtimeStatus() {
  const status = useWsStatus();
  const tone = TONES[status] ?? TONES.idle;
  return (
    <span
      className="flex items-center gap-1.5"
      title={`Realtime ${tone.label}`}
    >
      <span className="relative flex h-1.5 w-1.5">
        <span className={`absolute inline-flex h-full w-full rounded-full ${tone.dot}`} />
      </span>
      {tone.label}
    </span>
  );
}
