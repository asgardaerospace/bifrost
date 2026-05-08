"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useRecentEvents } from "@/lib/realtime-store";
import type { OperationalEventRead } from "@/types/api";

function relTime(iso: string | null | undefined) {
  if (!iso) return "—";
  const d = new Date(iso);
  const diff = Date.now() - d.getTime();
  const m = Math.round(diff / 60_000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h`;
  return `${Math.round(h / 24)}d`;
}

const SEVERITY_TONE: Record<string, string> = {
  info: "text-mute2",
  notice: "text-cyan",
  warning: "text-amber",
  critical: "text-red",
};

export function ExecutionRail() {
  const { data, isLoading } = useQuery({
    queryKey: ["operational-events", "recent"],
    queryFn: () => api.events({ limit: 30 }),
    staleTime: 10_000,
  });

  // Live events streamed via the websocket, newest-first.
  const liveEvents = useRecentEvents();

  // Merge persisted backfill (server-ascending) with live tail (newest-first),
  // dedup by id, and slice to the visible window. The live store survives
  // navigation so we don't blink the rail empty between routes.
  const recent: OperationalEventRead[] = useMemo(() => {
    const persisted = [...(data?.items ?? [])].reverse();
    const seen = new Set<number>();
    const merged: OperationalEventRead[] = [];
    for (const ev of [...liveEvents, ...persisted]) {
      if (seen.has(ev.id)) continue;
      seen.add(ev.id);
      merged.push(ev);
      if (merged.length >= 14) break;
    }
    return merged;
  }, [data, liveEvents]);

  const totalCount = (data?.count ?? 0) + liveEvents.length;

  return (
    <footer className="relative flex h-24 shrink-0 items-stretch border-t border-border/80 bg-panel/70 glass-strong">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent/40 to-transparent" />

      <div className="flex w-44 shrink-0 flex-col justify-center gap-1 border-r border-border/60 px-4">
        <span className="font-mono text-2xs uppercase tracking-[0.3em] text-accent/80">
          ▸ execution
        </span>
        <span className="font-mono text-2xs text-mute2">
          {totalCount} events
        </span>
        <span className="font-mono text-[10px] text-mute2">
          live · ws fanout
        </span>
      </div>

      <div className="flex-1 overflow-x-auto">
        <div className="flex h-full items-stretch gap-2 px-3 py-2">
          {isLoading && (
            <div className="self-center px-2 font-mono text-2xs text-mute2 animate-soft-pulse">
              ▸ syncing event log…
            </div>
          )}
          {!isLoading && recent.length === 0 && (
            <div className="self-center px-2 font-mono text-2xs text-mute2">
              event log clear
            </div>
          )}
          {recent.map((ev) => (
            <div
              key={ev.id}
              className="flex w-56 shrink-0 flex-col gap-1 rounded-md border border-border/60 bg-panel2/50 px-2 py-1.5"
            >
              <div className="flex items-center justify-between font-mono text-[10px] uppercase tracking-wider">
                <span className="truncate text-accent/80">
                  {ev.topic}
                </span>
                <span className={SEVERITY_TONE[ev.severity] ?? "text-mute2"}>
                  {ev.severity}
                </span>
              </div>
              <div className="line-clamp-2 text-[11px] text-ink">
                {ev.event_type}
              </div>
              <div className="font-mono text-[10px] text-mute2">
                {relTime(ev.created_at)}
              </div>
            </div>
          ))}
        </div>
      </div>
    </footer>
  );
}
