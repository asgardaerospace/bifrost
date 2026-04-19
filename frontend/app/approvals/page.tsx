"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ApprovalRead } from "@/types/api";
import {
  Empty,
  Panel,
  Pill,
  SourceBadge,
  formatDate,
  relative,
} from "@/components/ui";

const REVIEWER = "operator@asgard";

export default function ApprovalsPage() {
  const [statusFilter, setStatusFilter] = useState<string>("pending");
  const qc = useQueryClient();

  const approvals = useQuery({
    queryKey: ["approvals", statusFilter],
    queryFn: () => api.listApprovals(statusFilter || undefined, 100),
  });

  const [noteById, setNoteById] = useState<Record<number, string>>({});
  const [errorById, setErrorById] = useState<Record<number, string>>({});

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["approvals"] });
    qc.invalidateQueries({ queryKey: ["approvals-pending"] });
  };

  const approve = useMutation({
    mutationFn: (a: ApprovalRead) =>
      api.approveApproval(a.id, {
        reviewer: REVIEWER,
        decision_note: noteById[a.id] || undefined,
      }),
    onSuccess: () => invalidate(),
    onError: (e: Error, a) =>
      setErrorById((prev) => ({ ...prev, [a.id]: e.message })),
  });

  const reject = useMutation({
    mutationFn: (a: ApprovalRead) =>
      api.rejectApproval(a.id, {
        reviewer: REVIEWER,
        decision_note: noteById[a.id] || undefined,
      }),
    onSuccess: () => invalidate(),
    onError: (e: Error, a) =>
      setErrorById((prev) => ({ ...prev, [a.id]: e.message })),
  });

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">Approvals</h1>
        <p className="mt-1 text-sm text-muted">
          Send-approvals for communications. Drafts sourced from the
          investor engine are badged accordingly.
        </p>
      </header>

      <div className="flex items-center gap-2">
        {(["pending", "approved", "rejected", ""] as const).map((s) => (
          <button
            key={s || "all"}
            onClick={() => setStatusFilter(s)}
            className={
              "rounded border px-3 py-1 text-xs " +
              (statusFilter === s
                ? "border-accent bg-accent/10 text-ink"
                : "border-border text-muted hover:text-ink")
            }
          >
            {s || "all"}
          </button>
        ))}
      </div>

      <Panel title={`Approvals · ${approvals.data?.length ?? 0}`}>
        {approvals.isLoading ? (
          <Empty>Loading…</Empty>
        ) : !approvals.data || approvals.data.length === 0 ? (
          <Empty>No approvals.</Empty>
        ) : (
          <ul className="divide-y divide-border">
            {approvals.data.map((a) => {
              const isEngine = a.source_system === "investor_engine";
              const isPending = a.status === "pending";
              return (
                <li key={a.id} className="space-y-2 py-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">
                          {a.communication_subject ??
                            `${a.action} · ${a.entity_type} #${a.entity_id}`}
                        </span>
                        <SourceBadge
                          source={isEngine ? "investor_engine" : "bifrost"}
                        />
                        <Pill
                          tone={
                            a.status === "pending"
                              ? "warn"
                              : a.status === "approved"
                                ? "ok"
                                : a.status === "rejected"
                                  ? "danger"
                                  : "default"
                          }
                        >
                          {a.status}
                        </Pill>
                        {a.communication_status && (
                          <Pill tone="default">
                            comm · {a.communication_status}
                          </Pill>
                        )}
                      </div>
                      <div className="text-xs text-muted">
                        {a.action} · requested by {a.requested_by ?? "unknown"}
                        {" · "}
                        {relative(a.created_at)}
                        {a.reviewed_at && (
                          <>
                            {" · reviewed "}
                            {formatDate(a.reviewed_at)} by{" "}
                            {a.reviewer ?? "?"}
                          </>
                        )}
                      </div>
                      {isEngine && a.source_external_id && (
                        <div className="font-mono text-[10px] text-muted">
                          engine external_id:{" "}
                          <span className="break-all">
                            {a.source_external_id}
                          </span>
                        </div>
                      )}
                      {a.decision_note && (
                        <div className="text-xs italic text-muted">
                          “{a.decision_note}”
                        </div>
                      )}
                    </div>
                  </div>

                  {isPending && (
                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        value={noteById[a.id] ?? ""}
                        onChange={(e) =>
                          setNoteById((prev) => ({
                            ...prev,
                            [a.id]: e.target.value,
                          }))
                        }
                        placeholder="Decision note (optional)"
                        className="flex-1 rounded border border-border bg-bg/40 px-2 py-1 text-xs"
                      />
                      <button
                        onClick={() => approve.mutate(a)}
                        disabled={approve.isPending}
                        className="rounded bg-ok px-3 py-1 text-xs font-medium text-bg disabled:opacity-50"
                      >
                        Approve
                      </button>
                      <button
                        onClick={() => reject.mutate(a)}
                        disabled={reject.isPending}
                        className="rounded bg-danger px-3 py-1 text-xs font-medium text-bg disabled:opacity-50"
                      >
                        Reject
                      </button>
                    </div>
                  )}

                  {errorById[a.id] && (
                    <div className="rounded border border-danger/40 bg-danger/10 px-2 py-1 text-[11px] text-danger">
                      {errorById[a.id]}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </Panel>
    </div>
  );
}
