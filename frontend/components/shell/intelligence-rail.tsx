"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

function relTime(iso: string | null | undefined) {
  if (!iso) return "—";
  const d = new Date(iso);
  const diff = Date.now() - d.getTime();
  const m = Math.round(diff / 60_000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}

export function IntelligenceRail() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["intel-top-signals"],
    queryFn: () => api.intelTopSignals(20),
    staleTime: 30_000,
  });

  // intelTopSignals returns { generated_at, total, items: [...] }
  const items = data?.items ?? [];

  return (
    <aside className="relative flex h-full min-h-0 flex-col border-r border-accent/20 bg-panel/60 glass-strong">
      <div className="pointer-events-none absolute inset-y-0 right-0 w-px bg-gradient-to-b from-transparent via-accent/40 to-transparent" />

      <div className="flex items-center justify-between border-b border-border/80 px-3 py-2">
        <span className="font-mono text-2xs uppercase tracking-[0.3em] text-accent/80">
          ▸ intelligence
        </span>
        <span className="font-mono text-2xs text-mute2">
          {items.length} live
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        {isLoading && (
          <div className="animate-soft-pulse p-2 font-mono text-2xs text-mute2">
            ▸ syncing signal stream…
          </div>
        )}
        {error && (
          <div className="p-2 font-mono text-2xs text-red">
            signal stream unreachable
          </div>
        )}
        {!isLoading && items.length === 0 && (
          <div className="p-2 font-mono text-2xs text-mute2">
            no signals — quiet skies
          </div>
        )}
        <ul className="flex flex-col gap-1.5">
          {items.map((it) => (
            <li
              key={it.id}
              className="group rounded-md border border-border/60 bg-panel2/50 p-2 transition-colors hover:border-accent/40 hover:bg-panel3/60"
            >
              <div className="flex items-center justify-between font-mono text-[10px] uppercase tracking-wider text-mute2">
                <span className="truncate">{it.source}</span>
                <span>{relTime(it.published_at ?? it.created_at)}</span>
              </div>
              <div className="mt-1 line-clamp-2 text-xs text-ink group-hover:text-inkhi">
                {it.title}
              </div>
              <div className="mt-1 flex items-center gap-2 font-mono text-[10px]">
                <span className="chip">{it.category}</span>
                {it.region && <span className="chip">{it.region}</span>}
                <span className="ml-auto text-accent">
                  s{it.strategic_relevance_score}/u{it.urgency_score}
                </span>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}
