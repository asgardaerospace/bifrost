"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { CommunicationRead } from "@/types/api";
import { api } from "@/lib/api";
import { Pill, SourceBadge } from "@/components/ui";

const DEFAULT_ACTOR = "operator@asgard";

type CloseReason = "dismissed" | "approval_requested" | "edit_later";

export function DraftReviewModal({
  communication,
  onClose,
}: {
  communication: CommunicationRead;
  onClose: (reason: CloseReason) => void;
}) {
  const qc = useQueryClient();
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  const isEngineSourced = communication.source_system === "investor_engine";
  const isDraft = communication.status === "draft";

  const requestApproval = useMutation({
    mutationFn: () =>
      api.requestSendApproval(communication.id, {
        requested_by: DEFAULT_ACTOR,
        note: note || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["approvals-pending"] });
      qc.invalidateQueries({ queryKey: ["approvals"] });
      onClose("approval_requested");
    },
    onError: (e: Error) => setError(e.message),
  });

  return (
    <div
      className="fixed inset-0 z-40 flex items-start justify-center bg-black/60 p-6"
      onClick={() => onClose("dismissed")}
    >
      <div
        className="mt-12 w-full max-w-2xl rounded-lg border border-border bg-panel shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b border-border px-5 py-3">
          <div className="flex items-center gap-2">
            <h2 className="font-mono text-xs uppercase tracking-widest text-muted">
              Draft · review
            </h2>
            <SourceBadge
              source={isEngineSourced ? "investor_engine" : "bifrost"}
            />
            <Pill
              tone={
                communication.status === "draft"
                  ? "default"
                  : communication.status === "pending_approval"
                    ? "warn"
                    : communication.status === "sent"
                      ? "ok"
                      : "default"
              }
            >
              {communication.status}
            </Pill>
          </div>
          <button
            className="font-mono text-[11px] uppercase tracking-widest text-muted hover:text-ink"
            onClick={() => onClose("dismissed")}
          >
            Close ✕
          </button>
        </header>

        <div className="space-y-3 px-5 py-4">
          {isEngineSourced && (
            <div className="rounded border border-accent/30 bg-accent/5 px-3 py-2 text-xs">
              Draft generated from an{" "}
              <span className="font-semibold">Investor Engine</span>{" "}
              record. Approving it sends from Bifrost — no write-back to the
              investor engine.
              {communication.source_external_id && (
                <div className="mt-1 font-mono text-[10px] text-muted">
                  source_external_id:{" "}
                  <span className="break-all">
                    {communication.source_external_id}
                  </span>
                </div>
              )}
            </div>
          )}

          <dl className="grid grid-cols-[90px,1fr] gap-y-1 text-sm">
            <dt className="text-muted">To</dt>
            <dd className="break-all">{communication.to_address ?? "—"}</dd>
            <dt className="text-muted">From</dt>
            <dd className="break-all">{communication.from_address ?? "—"}</dd>
            <dt className="text-muted">Subject</dt>
            <dd className="font-medium">{communication.subject ?? "—"}</dd>
          </dl>

          <div className="rounded border border-border bg-bg/40 p-3">
            <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">
              {communication.body ?? "(empty body)"}
            </pre>
          </div>

          <label className="block">
            <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
              Approval note (optional)
            </span>
            <input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              disabled={!isDraft}
              placeholder="Why is this draft being sent now?"
              className="mt-1 w-full rounded border border-border bg-bg/40 px-2 py-1.5 text-sm"
            />
          </label>

          {error && (
            <div className="rounded border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">
              {error}
            </div>
          )}
        </div>

        <footer className="flex items-center justify-between border-t border-border px-5 py-3">
          <button
            onClick={() => onClose("edit_later")}
            className="rounded px-3 py-1.5 text-sm text-muted hover:text-ink"
          >
            Edit Later
          </button>
          <div className="flex items-center gap-2">
            <button
              onClick={() => onClose("dismissed")}
              className="rounded px-3 py-1.5 text-sm text-muted hover:text-ink"
            >
              Close
            </button>
            <button
              onClick={() => {
                setError(null);
                requestApproval.mutate();
              }}
              disabled={!isDraft || requestApproval.isPending}
              className="rounded bg-accent px-3 py-1.5 text-sm font-medium text-bg disabled:opacity-50"
            >
              {requestApproval.isPending ? "Requesting…" : "Request Approval"}
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}
