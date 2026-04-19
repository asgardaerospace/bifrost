"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { CommunicationRead } from "@/types/api";
import { DraftReviewModal } from "@/components/draft-review-modal";
import {
  Empty,
  Panel,
  Pill,
  SourceBadge,
  formatDate,
  relative,
} from "@/components/ui";

export default function EngineListPage() {
  const [stage, setStage] = useState("");
  const [followUp, setFollowUp] = useState("");
  const [owner, setOwner] = useState("");

  const [draft, setDraft] = useState<CommunicationRead | null>(null);
  const createDraft = useMutation({
    mutationFn: (externalId: string) =>
      api.engineCreateFollowUpDraft(externalId, { actor: "operator@asgard" }),
    onSuccess: (res) => setDraft(res.communication),
  });

  const investors = useQuery({
    queryKey: ["engine-list", stage, followUp, owner],
    queryFn: () =>
      api.engineList({
        stage: stage || undefined,
        follow_up_status: followUp || undefined,
        owner: owner || undefined,
        limit: 200,
      }),
  });

  const uniqueStages = useMemo(
    () =>
      Array.from(
        new Set((investors.data ?? []).map((n) => n.stage).filter(Boolean)),
      ) as string[],
    [investors.data],
  );
  const uniqueFollowUps = useMemo(
    () =>
      Array.from(
        new Set(
          (investors.data ?? []).map((n) => n.follow_up_status).filter(Boolean),
        ),
      ) as string[],
    [investors.data],
  );
  const uniqueOwners = useMemo(
    () =>
      Array.from(
        new Set((investors.data ?? []).map((n) => n.owner).filter(Boolean)),
      ) as string[],
    [investors.data],
  );

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold">Investor Engine</h1>
            <SourceBadge source="investor_engine" />
          </div>
          <p className="mt-1 text-sm text-muted">
            External system · read-only. Records here are not stored in
            Bifrost&apos;s native investor tables.
          </p>
        </div>
      </header>

      <Panel title="Filters">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <label className="flex flex-col gap-1">
            <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
              Stage
            </span>
            <select
              value={stage}
              onChange={(e) => setStage(e.target.value)}
              className="rounded border border-border bg-bg/40 px-2 py-1.5 text-sm"
            >
              <option value="">Any</option>
              {uniqueStages.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
              Follow-up status
            </span>
            <select
              value={followUp}
              onChange={(e) => setFollowUp(e.target.value)}
              className="rounded border border-border bg-bg/40 px-2 py-1.5 text-sm"
            >
              <option value="">Any</option>
              {uniqueFollowUps.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
              Owner
            </span>
            <select
              value={owner}
              onChange={(e) => setOwner(e.target.value)}
              className="rounded border border-border bg-bg/40 px-2 py-1.5 text-sm"
            >
              <option value="">Any</option>
              {uniqueOwners.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
        </div>
      </Panel>

      <Panel
        title={`Records${investors.data ? ` · ${investors.data.length}` : ""}`}
        right={<SourceBadge source="investor_engine" />}
      >
        {investors.isLoading ? (
          <Empty>Loading…</Empty>
        ) : !investors.data || investors.data.length === 0 ? (
          <Empty>No investor engine records match these filters.</Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left font-mono text-[10px] uppercase tracking-widest text-muted">
                  <th className="py-2 pr-3">Firm</th>
                  <th className="py-2 pr-3">Stage</th>
                  <th className="py-2 pr-3">Owner</th>
                  <th className="py-2 pr-3">Follow-up</th>
                  <th className="py-2 pr-3">Last touch</th>
                  <th className="py-2 pr-3">Next follow-up</th>
                  <th className="py-2 pr-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {investors.data.map((n) => (
                  <tr key={n.external_id} className="hover:bg-border/30">
                    <td className="py-2 pr-3">
                      <Link
                        href={`/engine/${encodeURIComponent(n.external_id)}`}
                        className="font-medium hover:underline"
                      >
                        {n.firm_name}
                      </Link>
                    </td>
                    <td className="py-2 pr-3">
                      {n.stage ? (
                        <Pill tone="default">{n.stage}</Pill>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td className="py-2 pr-3 text-muted">
                      {n.owner ?? "—"}
                    </td>
                    <td className="py-2 pr-3">
                      {n.follow_up_status ? (
                        <Pill
                          tone={
                            n.follow_up_status === "overdue"
                              ? "danger"
                              : n.follow_up_status === "due"
                                ? "warn"
                                : "default"
                          }
                        >
                          {n.follow_up_status}
                        </Pill>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td className="py-2 pr-3 text-muted">
                      {relative(n.last_touch_at)}
                    </td>
                    <td className="py-2 pr-3 text-muted">
                      {formatDate(n.next_follow_up_at)}
                    </td>
                    <td className="py-2 pr-3">
                      <button
                        onClick={() => createDraft.mutate(n.external_id)}
                        disabled={
                          createDraft.isPending &&
                          createDraft.variables === n.external_id
                        }
                        className="rounded border border-border px-2 py-1 text-[11px] hover:bg-border/50 disabled:opacity-50"
                      >
                        Draft
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {draft && (
        <DraftReviewModal
          communication={draft}
          onClose={() => setDraft(null)}
        />
      )}
    </div>
  );
}
