"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { CognitionResponseRead } from "@/types/api";

const SUGGESTED = [
  "show missions under rising pressure",
  "summarize supplier instability",
  "what changed operationally this week",
  "summarize aerospace funding movement",
  "show executive priorities",
];

function confidenceTone(c: number) {
  if (c >= 0.7) return "text-green";
  if (c >= 0.4) return "text-cyan";
  if (c > 0) return "text-amber";
  return "text-red";
}

/**
 * Embedded operational cognition surface — not a chatbot.
 *
 * Operators submit commands from a fixed prompt vocabulary. The pipeline
 * classifies the intent, plans retrieval, and returns a grounded synthesis
 * with citations + confidence + retrieval trace. No conversational state.
 */
export function CognitionPanel({ missionId }: { missionId?: number }) {
  const [command, setCommand] = useState("");
  const [response, setResponse] = useState<CognitionResponseRead | null>(null);

  const mutation = useMutation({
    mutationFn: (q: string) =>
      api.cognitionCommand({
        command: q,
        mission_id: missionId ?? null,
      }),
    onSuccess: (data) => setResponse(data),
  });

  function submit(q: string) {
    if (!q.trim()) return;
    setCommand(q);
    mutation.mutate(q.trim());
  }

  return (
    <section className="rounded-lg border border-border/60 bg-panel/60">
      <header className="flex items-center justify-between border-b border-border/60 px-4 py-3">
        <span className="font-mono text-2xs uppercase tracking-widest text-accent/80">
          ▸ operational cognition
        </span>
        <span className="font-mono text-2xs text-mute2">
          retrieval-grounded · no autonomous action
        </span>
      </header>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(command);
        }}
        className="flex gap-2 border-b border-border/60 p-3"
      >
        <input
          value={command}
          onChange={(e) => setCommand(e.target.value)}
          placeholder="ask the operational record…"
          className="flex-1 rounded-md border border-border bg-bgdeep px-3 py-2 text-sm text-inkhi outline-none focus:border-accent"
        />
        <button
          type="submit"
          disabled={!command.trim() || mutation.isPending}
          className="chip-accent rounded-md px-3 py-2 text-xs font-semibold uppercase tracking-widest hover:bg-accent/30 disabled:opacity-50"
        >
          {mutation.isPending ? "…" : "synthesize"}
        </button>
      </form>

      <div className="border-b border-border/60 px-4 py-2">
        <div className="mb-1 font-mono text-[10px] uppercase tracking-widest text-mute2">
          curated commands
        </div>
        <div className="flex flex-wrap gap-1.5">
          {SUGGESTED.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => submit(s)}
              className="rounded-md border border-border/60 bg-panel2/40 px-2 py-1 text-[11px] text-mute2 hover:border-accent/40 hover:text-accent"
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <div className="px-4 py-3">
        {!response && !mutation.isPending && (
          <div className="font-mono text-2xs text-mute2">
            ▸ awaiting command. responses cite sources, expose confidence, and
            refuse on weak retrieval.
          </div>
        )}
        {mutation.isPending && (
          <div className="animate-soft-pulse font-mono text-2xs text-mute2">
            ▸ classifying intent · retrieving · synthesizing…
          </div>
        )}
        {response && (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-3 font-mono text-2xs uppercase tracking-wider text-mute2">
              <span className="text-accent/80">
                {response.intent_label || "no intent matched"}
              </span>
              {response.intent_id && (
                <span title="matched keywords">
                  {response.matched_keywords.join(" · ")}
                </span>
              )}
              <span className={confidenceTone(response.intent_confidence)}>
                intent {Math.round(response.intent_confidence * 100)}%
              </span>
              <span
                className={confidenceTone(response.synthesis.confidence)}
                title="synthesis confidence"
              >
                synth {Math.round(response.synthesis.confidence * 100)}%
              </span>
              {response.synthesis.weak_retrieval && (
                <span className="text-amber">weak retrieval</span>
              )}
            </div>
            <pre className="whitespace-pre-wrap font-sans text-xs text-ink leading-relaxed">
              {response.synthesis.summary}
            </pre>
            {response.synthesis.citations.length > 0 && (
              <div className="border-t border-border/60 pt-3">
                <div className="mb-2 font-mono text-2xs uppercase tracking-widest text-mute2">
                  ▸ {response.synthesis.citations.length} citation
                  {response.synthesis.citations.length === 1 ? "" : "s"}
                </div>
                <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">
                  {response.synthesis.citations.map((c) => (
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
                        {c.title && <div className="font-medium">{c.title}</div>}
                        <div className="text-mute2">{c.excerpt}</div>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div className="border-t border-border/60 pt-2 font-mono text-[10px] uppercase tracking-wider text-mute2">
              ▸ trace · {response.synthesis.retrieval_trace.candidates_considered} candidates ·{" "}
              {response.synthesis.retrieval_trace.chunks_returned} returned ·{" "}
              {response.synthesis.retrieval_trace.embedding_model}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
