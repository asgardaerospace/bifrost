"use client";

import { useState } from "react";
import type { DraftOutput } from "@/types/api";
import { Panel, Pill, SourceBadge } from "@/components/ui";
import { api } from "@/lib/api";

export function DraftOutputView({ output }: { output: DraftOutput }) {
  const comm = output.communication;
  const [status, setStatus] = useState(comm.status);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function requestApproval() {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1"}/communications/${comm.id}/request-send-approval`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ requested_by: "ui" }),
        }
      );
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail ?? `Failed (${res.status})`);
      }
      setStatus("pending_approval");
      setMsg("Approval requested.");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel
      title="Draft"
      right={
        <span className="flex items-center gap-2">
          <SourceBadge
            source={
              comm.source_system === "investor_engine"
                ? "investor_engine"
                : "bifrost"
            }
          />
          <Pill tone={status === "pending_approval" ? "warn" : "default"}>
            {status}
          </Pill>
        </span>
      }
    >
      <div className="mb-2 text-base font-medium">{output.headline}</div>

      <div className="space-y-3">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-muted">
            Subject
          </div>
          <div className="mt-1">{comm.subject ?? "—"}</div>
        </div>
        <div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-muted">
            Body
          </div>
          <pre className="mt-1 whitespace-pre-wrap rounded-md border border-border bg-bg/40 p-3 font-sans text-sm">
            {comm.body ?? ""}
          </pre>
        </div>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-muted">
              To
            </div>
            <div>{comm.to_address ?? "—"}</div>
          </div>
          <div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-muted">
              Channel
            </div>
            <div>
              {comm.channel} · {comm.direction}
            </div>
          </div>
        </div>
      </div>

      <div className="mt-4 rounded-md border border-border bg-bg/40 p-3 text-sm">
        <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
          Rationale
        </span>
        <div className="mt-1">{output.rationale}</div>
      </div>

      {comm.source_system === "investor_engine" && comm.source_external_id && (
        <div className="mt-3 rounded border border-accent/30 bg-accent/5 px-3 py-2 text-xs">
          Originated from an <span className="font-semibold">Investor Engine</span>{" "}
          record. external_id:{" "}
          <span className="break-all font-mono text-[10px]">
            {comm.source_external_id}
          </span>
        </div>
      )}

      {output.missing_context.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {output.missing_context.map((m, i) => (
            <Pill key={i} tone="warn">
              missing: {m}
            </Pill>
          ))}
        </div>
      )}

      <div className="mt-4 flex items-center gap-3">
        <button
          onClick={requestApproval}
          disabled={busy || status !== "draft"}
          className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-bg disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy ? "Requesting…" : "Request approval"}
        </button>
        <button
          disabled
          title="Editing not yet implemented"
          className="rounded-md border border-border px-3 py-1.5 text-sm text-muted disabled:cursor-not-allowed"
        >
          Edit later
        </button>
        {msg && <span className="text-sm text-ok">{msg}</span>}
        {err && <span className="text-sm text-danger">{err}</span>}
      </div>
    </Panel>
  );
}
