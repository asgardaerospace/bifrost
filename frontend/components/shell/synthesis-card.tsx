"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { SynthesisResponseRead } from "@/types/api";

type SynthesisKind = "summary" | "pressure" | "history";

const KIND_LABEL: Record<SynthesisKind, string> = {
  summary: "Synthesize state",
  pressure: "Explain pressure",
  history: "Synthesize history",
};

function confidenceTone(c: number) {
  if (c >= 0.7) return "text-green";
  if (c >= 0.4) return "text-cyan";
  if (c > 0) return "text-amber";
  return "text-red";
}

/**
 * Retrieval-grounded synthesis surface.
 *
 * Doctrine: every output cites its sources, exposes confidence, and falls
 * back to "INSUFFICIENT CONTEXT" when retrieval is weak. There are no chat
 * boxes, no streaming text balloons — synthesis is rendered as a calm,
 * inline operational note with citation chips.
 */
export function SynthesisCard({ missionId }: { missionId: number }) {
  const [active, setActive] = useState<SynthesisKind | null>(null);
  const [response, setResponse] = useState<SynthesisResponseRead | null>(null);

  const mutation = useMutation({
    mutationFn: async (kind: SynthesisKind) => {
      setActive(kind);
      if (kind === "summary") return api.synthesizeMission(missionId);
      if (kind === "pressure") return api.synthesizePressure(missionId);
      return api.synthesizeHistory(missionId);
    },
    onSuccess: (data) => setResponse(data),
  });

  return (
    <section className="rounded-lg border border-border/60 bg-panel/60">
      <header className="flex items-center justify-between border-b border-border/60 px-4 py-3">
        <div className="flex items-center gap-2 font-mono text-2xs uppercase tracking-widest text-accent/80">
          <span>▸ grounded synthesis</span>
        </div>
        <div className="flex items-center gap-1">
          {(["summary", "pressure", "history"] as SynthesisKind[]).map((k) => (
            <button
              key={k}
              type="button"
              disabled={mutation.isPending}
              onClick={() => mutation.mutate(k)}
              className={
                "rounded-md border px-2.5 py-1 font-mono text-[10px] uppercase tracking-widest transition-colors " +
                (active === k && mutation.isPending
                  ? "border-accent text-accent animate-soft-pulse"
                  : "border-border/60 text-mute2 hover:border-accent/40 hover:text-accent")
              }
            >
              {KIND_LABEL[k]}
            </button>
          ))}
        </div>
      </header>

      <div className="px-4 py-3">
        {!response && !mutation.isPending && (
          <div className="font-mono text-2xs text-mute2">
            ▸ retrieval-grounded synthesis is read-only and always cites its
            sources. confidence is shown explicitly. no autonomous action.
          </div>
        )}

        {mutation.isPending && (
          <div className="animate-soft-pulse font-mono text-2xs text-mute2">
            ▸ retrieving operational context…
          </div>
        )}

        {response && (
          <div className="space-y-3">
            <div className="flex items-center justify-between font-mono text-2xs uppercase tracking-wider text-mute2">
              <span className="text-accent/80">{response.objective}</span>
              <span className="flex items-center gap-3">
                <span title={`Model: ${response.model}`}>{response.model}</span>
                <span className={confidenceTone(response.confidence)}>
                  conf {(response.confidence * 100).toFixed(0)}%
                </span>
                {response.weak_retrieval && (
                  <span className="text-amber">weak retrieval</span>
                )}
              </span>
            </div>

            <pre className="whitespace-pre-wrap font-sans text-xs text-ink leading-relaxed">
              {response.summary}
            </pre>

            {response.citations.length > 0 && (
              <div className="border-t border-border/60 pt-3">
                <div className="mb-2 font-mono text-2xs uppercase tracking-widest text-mute2">
                  ▸ {response.citations.length} citation
                  {response.citations.length === 1 ? "" : "s"}
                </div>
                <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">
                  {response.citations.map((c) => (
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
              ▸ retrieval trace · {response.retrieval_trace.candidates_considered} candidates
              {" · "}
              {response.retrieval_trace.chunks_returned} returned
              {" · "}
              {response.retrieval_trace.embedding_model}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
