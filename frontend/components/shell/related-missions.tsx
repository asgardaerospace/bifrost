"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

/**
 * Retrieval-driven similar missions. Pure retrieval — no LLM synthesis.
 * Used in the Memory tab to surface organizational continuity.
 */
export function RelatedMissions({ missionId }: { missionId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ["mission", missionId, "related"],
    queryFn: () => api.relatedMissions(missionId, 6),
    staleTime: 60_000,
  });

  return (
    <section className="rounded-lg border border-border/60 bg-panel/60">
      <header className="flex items-center justify-between border-b border-border/60 px-4 py-3">
        <span className="font-mono text-2xs uppercase tracking-widest text-accent/80">
          ▸ similar missions
        </span>
        <span className="font-mono text-2xs text-mute2">
          {data?.related.length ?? 0} via retrieval
        </span>
      </header>

      {isLoading && (
        <div className="px-4 py-6 text-center font-mono text-2xs text-mute2 animate-soft-pulse">
          ▸ scanning organizational memory…
        </div>
      )}

      {!isLoading && (data?.related.length ?? 0) === 0 && (
        <div className="px-4 py-6 text-center font-mono text-2xs text-mute2">
          no similar missions in memory yet
        </div>
      )}

      <ul className="divide-y divide-border/60">
        {(data?.related ?? []).map((r) => (
          <li key={r.mission_id} className="px-4 py-2">
            <div className="flex items-center justify-between">
              <Link
                href={`/missions/${r.mission_id}`}
                className="font-mono text-2xs uppercase tracking-wider text-accent/80 hover:text-accent"
              >
                {r.title || `mission #${r.mission_id}`}
              </Link>
              <span
                className="font-mono text-2xs text-mute2"
                title={`semantic ${r.components.semantic.toFixed(2)} · keyword ${r.components.keyword.toFixed(2)} · recency ${r.components.recency.toFixed(2)}`}
              >
                rel {r.score.toFixed(2)}
              </span>
            </div>
            {r.excerpt && (
              <div className="mt-1 line-clamp-2 text-xs text-mute2">
                {r.excerpt}
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
