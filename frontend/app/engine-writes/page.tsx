"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import type {
  EngineWriteStatus,
  PendingEngineWriteRead,
} from "@/types/api";
import { Empty, Panel, Pill, formatDate } from "@/components/ui";

const STATUSES: (EngineWriteStatus | "all")[] = [
  "all",
  "pending",
  "processing",
  "failed",
  "succeeded",
];

const TONE: Record<
  EngineWriteStatus,
  "default" | "warn" | "danger" | "ok" | "accent"
> = {
  pending: "warn",
  processing: "accent",
  succeeded: "ok",
  failed: "danger",
};

function Row({ row }: { row: PendingEngineWriteRead }) {
  const qc = useQueryClient();
  const retrigger = useMutation({
    mutationFn: () => api.engineRetriggerWrite(row.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["engine-writes"] }),
  });
  return (
    <tr className="border-b border-border">
      <td className="px-2 py-2 font-mono text-xs text-muted">#{row.id}</td>
      <td className="px-2 py-2">
        <Link
          href={`/engine/${encodeURIComponent(row.external_id)}`}
          className="font-mono text-xs hover:underline"
        >
          {row.external_id}
        </Link>
      </td>
      <td className="px-2 py-2">
        <Pill tone="default">{row.action_type}</Pill>
      </td>
      <td className="px-2 py-2">
        <Pill tone={TONE[row.status] ?? "default"}>{row.status}</Pill>
      </td>
      <td className="px-2 py-2 text-xs tabular-nums">{row.attempt_count}</td>
      <td className="px-2 py-2 text-xs text-muted">
        {formatDate(row.created_at)}
      </td>
      <td className="max-w-[280px] truncate px-2 py-2 text-xs text-danger">
        {row.last_error ?? ""}
      </td>
      <td className="px-2 py-2">
        {(row.status === "failed" || row.status === "pending") && (
          <button
            onClick={() => retrigger.mutate()}
            disabled={retrigger.isPending}
            className="rounded border border-border px-2 py-0.5 text-[11px] uppercase tracking-widest text-muted hover:text-ink disabled:opacity-50"
          >
            {retrigger.isPending ? "…" : "Run"}
          </button>
        )}
      </td>
    </tr>
  );
}

export default function EngineWritesPage() {
  const qc = useQueryClient();
  const [filter, setFilter] = useState<EngineWriteStatus | "all">("all");
  const writes = useQuery({
    queryKey: ["engine-writes", filter],
    queryFn: () =>
      api.engineListWrites({
        status: filter === "all" ? undefined : filter,
        limit: 200,
      }),
  });
  const runWorker = useMutation({
    mutationFn: () => api.engineRunWorker(25),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["engine-writes"] }),
  });

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Engine writes</h1>
        <button
          onClick={() => runWorker.mutate()}
          disabled={runWorker.isPending}
          className="rounded bg-accent px-3 py-1.5 text-sm font-medium text-bg disabled:opacity-50"
        >
          {runWorker.isPending ? "Running…" : "Run worker"}
        </button>
      </header>

      <div className="flex items-center gap-2">
        {STATUSES.map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={
              "rounded border px-2 py-1 font-mono text-[11px] uppercase tracking-widest " +
              (filter === s
                ? "border-accent text-accent"
                : "border-border text-muted hover:text-ink")
            }
          >
            {s}
          </button>
        ))}
      </div>

      <Panel title="Outbox">
        {writes.isLoading ? (
          <Empty>Loading…</Empty>
        ) : !writes.data || writes.data.length === 0 ? (
          <Empty>No writes match this filter.</Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left text-sm">
              <thead>
                <tr className="border-b border-border font-mono text-[10px] uppercase tracking-widest text-muted">
                  <th className="px-2 py-2">ID</th>
                  <th className="px-2 py-2">Investor</th>
                  <th className="px-2 py-2">Action</th>
                  <th className="px-2 py-2">Status</th>
                  <th className="px-2 py-2">Attempts</th>
                  <th className="px-2 py-2">Created</th>
                  <th className="px-2 py-2">Last error</th>
                  <th className="px-2 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {writes.data.map((r) => (
                  <Row key={r.id} row={r} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}
