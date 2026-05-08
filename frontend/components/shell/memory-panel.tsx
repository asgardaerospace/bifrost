"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { RetrievalResultRead, SearchResponse } from "@/types/api";

const SOURCE_LABEL: Record<string, string> = {
  mission: "Mission",
  operational_event: "Event",
  approval: "Approval",
  execution_queue_item: "Queue",
  communication: "Comm",
  intel_item: "Intel",
  note: "Note",
  document: "Doc",
};

function relTime(iso?: string | null) {
  if (!iso) return "—";
  const d = new Date(iso);
  const diff = Date.now() - d.getTime();
  const m = Math.round(diff / 60_000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h`;
  return `${Math.round(h / 24)}d`;
}

function ResultRow({ r }: { r: RetrievalResultRead }) {
  return (
    <li className="rounded-md border border-border/60 bg-panel2/40 p-2 hover:border-accent/40">
      <div className="flex items-center justify-between font-mono text-[10px] uppercase tracking-wider text-mute2">
        <span className="text-accent/80">
          {SOURCE_LABEL[r.source_type] ?? r.source_type}#{r.source_id}
        </span>
        <span>{relTime(r.occurred_at)}</span>
      </div>
      {r.title && (
        <div className="mt-1 text-xs font-medium text-ink">{r.title}</div>
      )}
      <div className="mt-1 line-clamp-3 text-xs text-mute2">{r.text}</div>
      <div
        className="mt-1 flex items-center gap-2 font-mono text-[10px] text-mute2"
        title={`sem ${r.components.semantic.toFixed(2)} · kw ${r.components.keyword.toFixed(2)} · rec ${r.components.recency.toFixed(2)}`}
      >
        <span>score {r.score.toFixed(2)}</span>
        <span>·</span>
        <span>chunk {r.chunk_index}</span>
      </div>
    </li>
  );
}

/**
 * Memory tab content for the mission detail page.
 *
 * Top: retrieval-driven "related operational context" — read-only search
 * scoped to the mission. Operators can refine with a free-text query.
 * Below: sticky list of all memory records ingested for this mission.
 */
export function MemoryPanel({ missionId }: { missionId: number }) {
  const [query, setQuery] = useState("");

  const { data: missionMemory } = useQuery({
    queryKey: ["mission", missionId, "memory"],
    queryFn: () => api.memoryForMission(missionId, 100),
    staleTime: 30_000,
  });

  const search = useMutation<SearchResponse, Error, string>({
    mutationFn: (q: string) =>
      api.searchMemory({ query: q, mission_id: missionId, limit: 8 }),
  });

  function onSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    search.mutate(query.trim());
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <section className="rounded-lg border border-border/60 bg-panel/60">
        <header className="flex items-center justify-between border-b border-border/60 px-4 py-3">
          <span className="font-mono text-2xs uppercase tracking-widest text-accent/80">
            ▸ retrieve from mission memory
          </span>
          <span className="font-mono text-2xs text-mute2">
            mission #{missionId}
          </span>
        </header>
        <form onSubmit={onSearch} className="flex gap-2 border-b border-border/60 p-3">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask the operational record…"
            className="flex-1 rounded-md border border-border bg-bgdeep px-3 py-2 text-sm text-inkhi outline-none focus:border-accent"
          />
          <button
            type="submit"
            disabled={!query.trim() || search.isPending}
            className="chip-accent rounded-md px-3 py-2 text-xs font-semibold uppercase tracking-widest hover:bg-accent/30 disabled:opacity-50"
          >
            {search.isPending ? "…" : "retrieve"}
          </button>
        </form>
        <div className="px-4 py-3">
          {!search.data && !search.isPending && (
            <div className="font-mono text-2xs text-mute2">
              ▸ ranked by semantic + keyword + recency. results never leave the
              system. retrieval before generation.
            </div>
          )}
          {search.isPending && (
            <div className="animate-soft-pulse font-mono text-2xs text-mute2">
              ▸ retrieving…
            </div>
          )}
          {search.data && (
            <>
              <div className="mb-2 font-mono text-2xs text-mute2">
                ▸ {search.data.results.length} results from{" "}
                {search.data.trace.candidates_considered} candidates · model{" "}
                {search.data.trace.embedding_model}
              </div>
              <ul className="flex flex-col gap-2">
                {search.data.results.map((r) => (
                  <ResultRow key={r.chunk_id} r={r} />
                ))}
              </ul>
            </>
          )}
        </div>
      </section>

      <section className="rounded-lg border border-border/60 bg-panel/60">
        <header className="flex items-center justify-between border-b border-border/60 px-4 py-3">
          <span className="font-mono text-2xs uppercase tracking-widest text-accent/80">
            ▸ ingested memory records
          </span>
          <span className="font-mono text-2xs text-mute2">
            {missionMemory?.length ?? 0} records
          </span>
        </header>
        <ul className="max-h-[480px] divide-y divide-border/60 overflow-y-auto">
          {(missionMemory ?? []).map((m) => (
            <li key={m.id} className="px-4 py-2">
              <div className="flex items-center justify-between font-mono text-2xs uppercase tracking-wider text-mute2">
                <span className="text-accent/80">
                  {SOURCE_LABEL[m.source_type] ?? m.source_type}#{m.source_id}
                </span>
                <span>v{m.version} · {m.embedding_status}</span>
              </div>
              {m.title && (
                <div className="mt-1 text-xs font-medium text-ink">
                  {m.title}
                </div>
              )}
              <div className="mt-1 line-clamp-2 text-xs text-mute2">
                {m.content}
              </div>
            </li>
          ))}
          {(missionMemory?.length ?? 0) === 0 && (
            <li className="px-4 py-8 text-center font-mono text-2xs text-mute2">
              no memory ingested yet for this mission
            </li>
          )}
        </ul>
      </section>
    </div>
  );
}
