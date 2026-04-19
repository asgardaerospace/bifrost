"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import type {
  EngineWriteAction,
  EngineWriteStatus,
  PendingEngineWriteRead,
} from "@/types/api";
import { Empty, Panel, Pill, formatDate } from "@/components/ui";

const STATUS_TONE: Record<
  EngineWriteStatus,
  "default" | "warn" | "danger" | "ok" | "accent"
> = {
  pending: "warn",
  processing: "accent",
  succeeded: "ok",
  failed: "danger",
};

const ACTION_OPTIONS: { value: EngineWriteAction; label: string }[] = [
  { value: "update_follow_up", label: "Update follow-up" },
  { value: "log_touch", label: "Log touch" },
  { value: "update_stage", label: "Update stage" },
];

function defaultPayload(action: EngineWriteAction): string {
  if (action === "update_follow_up") {
    return JSON.stringify(
      { next_follow_up_at: new Date().toISOString(), completed: false },
      null,
      2,
    );
  }
  if (action === "log_touch") {
    return JSON.stringify(
      {
        touch_at: new Date().toISOString(),
        channel: "email",
        summary: "Outreach sent",
        author: "operator@asgard",
      },
      null,
      2,
    );
  }
  return JSON.stringify({ stage: "qualified", next_step: "Schedule demo" }, null, 2);
}

function WriteRow({ row }: { row: PendingEngineWriteRead }) {
  const qc = useQueryClient();
  const retrigger = useMutation({
    mutationFn: () => api.engineRetriggerWrite(row.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["engine-writes"] });
      qc.invalidateQueries({ queryKey: ["engine-writes-investor"] });
    },
  });

  return (
    <li className="flex flex-col gap-1 py-2">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Pill tone="default">{row.action_type}</Pill>
          <Pill tone={STATUS_TONE[row.status] ?? "default"}>{row.status}</Pill>
          <span className="font-mono text-[11px] text-muted">
            #{row.id} · attempts {row.attempt_count}
          </span>
        </div>
        {(row.status === "failed" || row.status === "pending") && (
          <button
            onClick={() => retrigger.mutate()}
            disabled={retrigger.isPending}
            className="rounded border border-border px-2 py-0.5 text-[11px] uppercase tracking-widest text-muted hover:text-ink disabled:opacity-50"
          >
            {retrigger.isPending ? "…" : "Run"}
          </button>
        )}
      </div>
      <div className="font-mono text-[11px] text-muted">
        {row.external_id} · created {formatDate(row.created_at)}
        {row.executed_at ? ` · executed ${formatDate(row.executed_at)}` : ""}
      </div>
      {row.last_error && (
        <div className="rounded border border-danger/40 bg-danger/10 px-2 py-1 text-[11px] text-danger">
          {row.last_error}
        </div>
      )}
    </li>
  );
}

export function EngineWritesPanel({ externalId }: { externalId: string }) {
  const qc = useQueryClient();
  const [action, setAction] = useState<EngineWriteAction>("update_follow_up");
  const [payloadText, setPayloadText] = useState<string>(
    defaultPayload("update_follow_up"),
  );
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const writes = useQuery({
    queryKey: ["engine-writes-investor", externalId],
    queryFn: () => api.engineWritesForInvestor(externalId, 25),
  });

  const requestWrite = useMutation({
    mutationFn: () => {
      let parsed: Record<string, unknown>;
      try {
        parsed = JSON.parse(payloadText) as Record<string, unknown>;
      } catch {
        throw new Error("Payload is not valid JSON");
      }
      return api.engineRequestWrite(externalId, {
        action_type: action,
        payload: parsed,
        requested_by: "operator@asgard",
      });
    },
    onSuccess: (a) => {
      setError(null);
      setInfo(`Approval #${a.id} created — pending review.`);
      qc.invalidateQueries({ queryKey: ["engine-writes-investor", externalId] });
      qc.invalidateQueries({ queryKey: ["approvals"] });
    },
    onError: (e: Error) => {
      setInfo(null);
      setError(e.message);
    },
  });

  return (
    <Panel title="Engine writes" right={<Pill tone="default">approval-gated</Pill>}>
      <div className="space-y-3">
        <div className="space-y-2 rounded border border-border bg-bg/40 p-3">
          <div className="flex items-center gap-2">
            <label className="font-mono text-[11px] uppercase tracking-widest text-muted">
              Action
            </label>
            <select
              value={action}
              onChange={(e) => {
                const next = e.target.value as EngineWriteAction;
                setAction(next);
                setPayloadText(defaultPayload(next));
              }}
              className="rounded border border-border bg-bg px-2 py-1 text-sm"
            >
              {ACTION_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <textarea
            value={payloadText}
            onChange={(e) => setPayloadText(e.target.value)}
            rows={6}
            className="w-full rounded border border-border bg-bg p-2 font-mono text-xs"
          />
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-muted">
              Submitting requests an approval. No write happens until approved.
            </span>
            <button
              onClick={() => requestWrite.mutate()}
              disabled={requestWrite.isPending}
              className="rounded bg-accent px-3 py-1 text-sm font-medium text-bg disabled:opacity-50"
            >
              {requestWrite.isPending ? "Requesting…" : "Request approval"}
            </button>
          </div>
          {error && (
            <div className="rounded border border-danger/40 bg-danger/10 px-2 py-1 text-[11px] text-danger">
              {error}
            </div>
          )}
          {info && (
            <div className="rounded border border-ok/40 bg-ok/10 px-2 py-1 text-[11px] text-ok">
              {info}
            </div>
          )}
        </div>

        <div>
          <div className="mb-1 font-mono text-[11px] uppercase tracking-widest text-muted">
            Recent writes
          </div>
          {writes.isLoading ? (
            <Empty>Loading…</Empty>
          ) : !writes.data || writes.data.length === 0 ? (
            <Empty>No writes recorded.</Empty>
          ) : (
            <ul className="divide-y divide-border">
              {writes.data.map((r) => (
                <WriteRow key={r.id} row={r} />
              ))}
            </ul>
          )}
        </div>
      </div>
    </Panel>
  );
}
