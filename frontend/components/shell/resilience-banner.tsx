"use client";

/**
 * Operational resilience banner.
 *
 * Sprint 8 — calm, non-intrusive surface for degraded state. Shown only
 * when the realtime layer has been disconnected long enough that operators
 * should know the surface is potentially stale. Avoids modals, sounds, and
 * red splashes — aerospace doctrine: failure states are calm and observable,
 * never alarming.
 */

import { useEffect, useState } from "react";

import { useRealtimeStore } from "@/lib/realtime-store";

const DEGRADED_GRACE_MS = 8_000;       // don't surface during a quick blip
const STALE_THRESHOLD_MS = 60_000;     // last frame older than this = stale

function formatAge(ms: number): string {
  if (ms < 60_000) return `${Math.round(ms / 1000)}s`;
  if (ms < 3_600_000) return `${Math.round(ms / 60_000)}m`;
  return `${Math.round(ms / 3_600_000)}h`;
}

export function ResilienceBanner() {
  const status = useRealtimeStore((s) => s.status);
  const lastSyncAt = useRealtimeStore((s) => s.lastSyncAt);
  const reconnectCount = useRealtimeStore((s) => s.reconnectCount);
  const degradedSince = useRealtimeStore((s) => s.degradedSince);
  const hasEverConnected = useRealtimeStore((s) => s.hasEverConnected);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 4000);
    return () => clearInterval(t);
  }, []);

  if (!hasEverConnected) return null;
  if (status === "open") {
    if (lastSyncAt && now - lastSyncAt > STALE_THRESHOLD_MS) {
      return (
        <div
          className="border-y border-amber/30 bg-amber/5 px-4 py-1.5 text-[11px] text-amber/90"
          role="status"
          aria-live="polite"
        >
          <span className="font-mono">REALTIME · QUIET</span>
          <span className="ml-3 text-amber/70">
            Last sync {formatAge(now - lastSyncAt)} ago — surface may be stale.
          </span>
        </div>
      );
    }
    return null;
  }

  if (!degradedSince) return null;
  const downFor = now - degradedSince;
  if (downFor < DEGRADED_GRACE_MS) return null;

  return (
    <div
      className="border-y border-amber/30 bg-amber/5 px-4 py-1.5 text-[11px] text-amber/90"
      role="status"
      aria-live="polite"
    >
      <span className="font-mono">REALTIME · RECONNECTING</span>
      <span className="ml-3 text-amber/70">
        Disconnected for {formatAge(downFor)}. Data will resync automatically.
        {reconnectCount > 0 && (
          <span className="ml-2 opacity-70">
            ({reconnectCount} prior reconnect{reconnectCount === 1 ? "" : "s"})
          </span>
        )}
      </span>
    </div>
  );
}
