"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";

function confidenceTone(c: number) {
  if (c >= 0.7) return "text-green";
  if (c >= 0.4) return "text-cyan";
  if (c > 0) return "text-amber";
  return "text-red";
}

const HOURS_OPTIONS = [12, 24, 72, 168];

/**
 * Daily executive intelligence briefing — grounded RAG synthesis with
 * citations and explicit confidence. Renders inline (no chat UX).
 */
export function ExecutiveBriefPanel() {
  const qc = useQueryClient();
  const [hours, setHours] = useState(24);
  const [ingesting, setIngesting] = useState(false);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["executive", "intelligence-brief", hours],
    queryFn: () => api.executiveBrief(hours),
    staleTime: 60_000,
  });

  async function ingestSeed() {
    setIngesting(true);
    try {
      await api.triggerIntelligenceIngest("aerospace_seed", "operator");
      qc.invalidateQueries({ queryKey: ["executive", "intelligence-brief"] });
      qc.invalidateQueries({ queryKey: ["intelligence-signals"] });
      qc.invalidateQueries({ queryKey: ["mission"] });
      refetch();
    } finally {
      setIngesting(false);
    }
  }

  return (
    <section className="rounded-lg border border-border/60 bg-panel/60">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 px-4 py-3">
        <div className="flex items-center gap-2 font-mono text-2xs uppercase tracking-widest text-accent/80">
          <span>▸ executive intelligence briefing</span>
        </div>
        <div className="flex items-center gap-2">
          {HOURS_OPTIONS.map((h) => (
            <button
              key={h}
              type="button"
              onClick={() => setHours(h)}
              className={
                "rounded-md border px-2 py-1 font-mono text-[10px] uppercase tracking-widest transition-colors " +
                (hours === h
                  ? "border-accent text-accent"
                  : "border-border/60 text-mute2 hover:border-accent/40 hover:text-accent")
              }
            >
              {h}h
            </button>
          ))}
          <button
            type="button"
            onClick={ingestSeed}
            disabled={ingesting}
            className="chip-accent rounded-md px-3 py-1 font-mono text-[10px] uppercase tracking-widest hover:bg-accent/30 disabled:opacity-50"
            title="Run the curated aerospace seed provider"
          >
            {ingesting ? "ingesting…" : "+ ingest seed"}
          </button>
        </div>
      </header>

      <div className="px-4 py-4">
        {isLoading && (
          <div className="animate-soft-pulse font-mono text-2xs text-mute2">
            ▸ retrieving operational movement…
          </div>
        )}

        {data && (
          <div className="space-y-3">
            <div className="flex items-center justify-between font-mono text-2xs uppercase tracking-wider text-mute2">
              <span className="text-accent/80">{data.objective}</span>
              <span className="flex items-center gap-3">
                <span title={`Model: ${data.model}`}>{data.model}</span>
                <span className={confidenceTone(data.confidence)}>
                  conf {(data.confidence * 100).toFixed(0)}%
                </span>
                {data.weak_retrieval && (
                  <span className="text-amber">weak retrieval</span>
                )}
              </span>
            </div>

            <pre className="whitespace-pre-wrap font-sans text-xs text-ink leading-relaxed">
              {data.summary}
            </pre>

            {data.citations.length > 0 && (
              <div className="border-t border-border/60 pt-3">
                <div className="mb-2 font-mono text-2xs uppercase tracking-widest text-mute2">
                  ▸ {data.citations.length} citation
                  {data.citations.length === 1 ? "" : "s"}
                </div>
                <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">
                  {data.citations.map((c) => (
                    <li
                      key={c.marker}
                      className="rounded-md border border-border/60 bg-panel2/40 p-2"
                    >
                      <div className="flex items-center justify-between font-mono text-2xs uppercase tracking-wider text-mute2">
                        <span className="text-accent/80">{c.marker}</span>
                        <span>
                          {c.source_type}#{c.source_id}
                        </span>
                      </div>
                      <div className="mt-1 line-clamp-3 text-xs text-ink">
                        {c.title && (
                          <div className="font-medium">{c.title}</div>
                        )}
                        <div className="text-mute2">{c.excerpt}</div>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="border-t border-border/60 pt-2 font-mono text-[10px] uppercase tracking-wider text-mute2">
              ▸ retrieval trace ·{" "}
              {data.retrieval_trace.candidates_considered} candidates ·{" "}
              {data.retrieval_trace.chunks_returned} returned ·{" "}
              {data.retrieval_trace.embedding_model}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
