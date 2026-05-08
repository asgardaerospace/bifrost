"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { AgentWorkflowStageRead } from "@/types/api";

const STAGE_TONE: Record<string, string> = {
  running: "text-cyan",
  completed: "text-green",
  failed: "text-red",
  skipped: "text-mute2",
  cancelled: "text-amber",
};

function StageRow({ stage }: { stage: AgentWorkflowStageRead }) {
  const tone = STAGE_TONE[stage.status] ?? "text-mute2";
  return (
    <li className="rounded-md border border-border/60 bg-panel2/40 p-3">
      <header className="flex items-center justify-between font-mono text-[10px] uppercase tracking-wider text-mute2">
        <div className="flex items-center gap-2">
          <span className="text-accent/80">stage {stage.stage_index}</span>
          <span className="text-ink">{stage.stage_name}</span>
        </div>
        <div className="flex items-center gap-3">
          {stage.confidence !== null && stage.confidence !== undefined && (
            <span>conf {stage.confidence}</span>
          )}
          <span className={tone}>{stage.status}</span>
        </div>
      </header>

      {stage.started_at && stage.completed_at && (
        <div className="mt-1 font-mono text-[10px] text-mute2">
          {new Date(stage.started_at).toLocaleTimeString()} →{" "}
          {new Date(stage.completed_at).toLocaleTimeString()}
        </div>
      )}

      {stage.error && (
        <div className="mt-2 rounded-md border border-red/40 bg-red/10 px-2 py-1 font-mono text-[10px] text-red">
          {stage.error}
        </div>
      )}

      {stage.output_payload && (
        <details className="mt-2">
          <summary className="cursor-pointer font-mono text-[10px] uppercase tracking-widest text-mute2 hover:text-accent">
            output payload
          </summary>
          <pre className="mt-1 max-h-40 overflow-auto rounded-md bg-bgdeep/60 p-2 font-mono text-[10px] text-ink">
            {JSON.stringify(stage.output_payload, null, 2)}
          </pre>
        </details>
      )}

      {stage.retrieval_trace && (
        <details className="mt-2">
          <summary className="cursor-pointer font-mono text-[10px] uppercase tracking-widest text-mute2 hover:text-accent">
            retrieval trace
          </summary>
          <pre className="mt-1 max-h-40 overflow-auto rounded-md bg-bgdeep/60 p-2 font-mono text-[10px] text-ink">
            {JSON.stringify(stage.retrieval_trace, null, 2)}
          </pre>
        </details>
      )}
    </li>
  );
}

export function WorkflowTraceViewer({ operationId }: { operationId: number | null }) {
  const qc = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ["agent-runs", operationId, "trace"],
    queryFn: () =>
      operationId !== null ? api.getAgentRunTrace(operationId) : Promise.resolve(null),
    enabled: operationId !== null,
    staleTime: 5_000,
  });

  const cancel = useMutation({
    mutationFn: () =>
      operationId !== null
        ? api.cancelAgentRun(operationId)
        : Promise.reject(new Error("no run selected")),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["agent-runs"] });
    },
  });

  if (operationId === null) {
    return (
      <section className="rounded-lg border border-border/60 bg-panel/40 p-8 text-center font-mono text-2xs uppercase tracking-widest text-accent/70">
        ▸ select a run to inspect its workflow trace
      </section>
    );
  }

  if (isLoading || !data) {
    return (
      <section className="rounded-lg border border-border/60 bg-panel/60 p-8 text-center font-mono text-2xs text-mute2 animate-soft-pulse">
        ▸ loading trace #{operationId}…
      </section>
    );
  }

  if (error) {
    return (
      <section className="rounded-lg border border-red/40 bg-red/10 p-4 font-mono text-2xs text-red">
        trace unreachable
      </section>
    );
  }

  const op = data.operation;
  const runStatusTone = STAGE_TONE[op.status] ?? "text-mute2";
  const cancellable = op.status === "running" || op.status === "proposed";

  return (
    <section className="rounded-lg border border-border/60 bg-panel/60">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="font-mono text-2xs uppercase tracking-widest text-accent/80">
            ▸ workflow trace
          </span>
          <span className="font-mono text-2xs text-mute2">
            #{op.id} · {op.agent_name}
          </span>
        </div>
        <div className="flex items-center gap-3 font-mono text-2xs text-mute2">
          <span className={runStatusTone}>{op.status}</span>
          <span>conf {op.confidence_score}</span>
          <span>stages {data.stages.length}</span>
          <span>actions {data.proposed_action_count}</span>
          {cancellable && (
            <button
              type="button"
              onClick={() => cancel.mutate()}
              disabled={cancel.isPending}
              className="rounded-md border border-amber/40 bg-amber/10 px-3 py-1 font-mono text-[10px] uppercase tracking-widest text-amber hover:bg-amber/20 disabled:opacity-40"
            >
              {cancel.isPending ? "…" : "cancel"}
            </button>
          )}
        </div>
      </header>

      <div className="grid grid-cols-1 gap-3 p-3 lg:grid-cols-[1fr_320px]">
        <ul className="flex flex-col gap-2">
          {data.stages.map((s) => (
            <StageRow key={s.id} stage={s} />
          ))}
          {data.stages.length === 0 && (
            <li className="rounded-md border border-border/60 bg-panel2/40 px-3 py-4 text-center font-mono text-2xs text-mute2">
              run produced no stage trace
            </li>
          )}
        </ul>

        <aside className="rounded-md border border-border/60 bg-panel2/40 p-3 font-mono text-[10px] text-mute2">
          <div className="mb-1 uppercase tracking-widest text-accent/80">
            run metadata
          </div>
          <dl className="grid grid-cols-[max-content_1fr] gap-x-2 gap-y-1">
            <dt>workflow</dt>
            <dd className="text-ink">{op.workflow_key ?? "—"}</dd>
            <dt>trigger</dt>
            <dd className="text-ink">{op.trigger ?? "—"}</dd>
            <dt>mission</dt>
            <dd className="text-ink">{op.mission_id ?? "—"}</dd>
            <dt>started</dt>
            <dd className="text-ink">
              {new Date(op.proposed_at).toLocaleString()}
            </dd>
            <dt>decided</dt>
            <dd className="text-ink">
              {op.decided_at ? new Date(op.decided_at).toLocaleString() : "—"}
            </dd>
          </dl>
          {op.reasoning && (
            <p className="mt-3 border-t border-border/60 pt-2 leading-relaxed text-mute2">
              {op.reasoning}
            </p>
          )}
        </aside>
      </div>
    </section>
  );
}
