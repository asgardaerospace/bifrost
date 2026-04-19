"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import type { CommunicationRead } from "@/types/api";
import {
  Empty,
  Panel,
  Pill,
  SourceBadge,
  formatDate,
  relative,
} from "@/components/ui";
import { DraftReviewModal } from "@/components/draft-review-modal";
import { EngineWritesPanel } from "@/components/engine-writes-panel";

export default function EngineDetailPage() {
  const params = useParams<{ id: string }>();
  const externalId = decodeURIComponent(params.id);

  const investor = useQuery({
    queryKey: ["engine-detail", externalId],
    queryFn: () => api.engineGet(externalId),
  });

  const [draft, setDraft] = useState<CommunicationRead | null>(null);
  const [draftError, setDraftError] = useState<string | null>(null);

  const createDraft = useMutation({
    mutationFn: () =>
      api.engineCreateFollowUpDraft(externalId, {
        actor: "operator@asgard",
      }),
    onSuccess: (res) => {
      setDraftError(null);
      setDraft(res.communication);
    },
    onError: (e: Error) => setDraftError(e.message),
  });

  if (investor.isLoading) {
    return <Empty>Loading engine record…</Empty>;
  }
  if (investor.isError || !investor.data) {
    return (
      <div className="space-y-3">
        <Link
          href="/engine"
          className="font-mono text-[11px] uppercase tracking-widest text-muted hover:text-ink"
        >
          ← Engine list
        </Link>
        <Empty>No investor engine record with external_id={externalId}.</Empty>
      </div>
    );
  }

  const n = investor.data;
  const primary = n.contacts[0];

  return (
    <div className="space-y-4">
      <div>
        <Link
          href="/engine"
          className="font-mono text-[11px] uppercase tracking-widest text-muted hover:text-ink"
        >
          ← Engine list
        </Link>
      </div>

      <header className="flex items-start justify-between gap-4">
        <div className="flex shrink-0 flex-col items-end gap-2">
          <button
            onClick={() => createDraft.mutate()}
            disabled={createDraft.isPending}
            className="rounded bg-accent px-3 py-1.5 text-sm font-medium text-bg disabled:opacity-50"
          >
            {createDraft.isPending ? "Creating…" : "Create Follow-Up Draft"}
          </button>
          {draftError && (
            <div className="rounded border border-danger/40 bg-danger/10 px-2 py-1 text-[11px] text-danger">
              {draftError}
            </div>
          )}
        </div>
        <div className="min-w-0 order-first">
          <div className="flex items-center gap-2">
            <h1 className="truncate text-xl font-semibold">{n.firm_name}</h1>
            <SourceBadge source="investor_engine" />
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted">
            {n.stage && <Pill tone="default">{n.stage}</Pill>}
            {n.follow_up_status && (
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
            )}
            {n.owner && <span>owner · {n.owner}</span>}
          </div>
          <p className="mt-2 text-xs text-muted">
            External record · read-only. This data is owned by the investor
            engine and surfaced through the Bifrost integration layer.
          </p>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Execution state">
          <dl className="grid grid-cols-[140px,1fr] gap-y-2 text-sm">
            <dt className="text-muted">Stage</dt>
            <dd>{n.stage ?? "—"}</dd>
            <dt className="text-muted">Owner</dt>
            <dd>{n.owner ?? "—"}</dd>
            <dt className="text-muted">Last touch</dt>
            <dd>
              {formatDate(n.last_touch_at)}{" "}
              <span className="text-xs text-muted">
                ({relative(n.last_touch_at)})
              </span>
            </dd>
            <dt className="text-muted">Next follow-up</dt>
            <dd>{formatDate(n.next_follow_up_at)}</dd>
            <dt className="text-muted">Next step</dt>
            <dd className="whitespace-pre-wrap">{n.next_step ?? "—"}</dd>
          </dl>
        </Panel>

        <Panel title="Primary contact">
          {!primary ? (
            <Empty>No contact on record.</Empty>
          ) : (
            <dl className="grid grid-cols-[140px,1fr] gap-y-2 text-sm">
              <dt className="text-muted">Name</dt>
              <dd>{primary.name}</dd>
              <dt className="text-muted">Title</dt>
              <dd>{primary.title ?? "—"}</dd>
              <dt className="text-muted">Email</dt>
              <dd>
                {primary.email ? (
                  <a
                    className="hover:underline"
                    href={`mailto:${primary.email}`}
                  >
                    {primary.email}
                  </a>
                ) : (
                  "—"
                )}
              </dd>
              <dt className="text-muted">Phone</dt>
              <dd>{primary.phone ?? "—"}</dd>
              <dt className="text-muted">LinkedIn</dt>
              <dd>
                {primary.linkedin_url ? (
                  <a
                    className="hover:underline"
                    href={primary.linkedin_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    profile
                  </a>
                ) : (
                  "—"
                )}
              </dd>
            </dl>
          )}
        </Panel>

        <Panel title="Recent activity" right={<SourceBadge source="investor_engine" />}>
          {n.recent_activity.length === 0 ? (
            <Empty>No activity synced.</Empty>
          ) : (
            <ul className="divide-y divide-border">
              {n.recent_activity.map((a) => (
                <li key={a.external_id} className="py-2">
                  <div className="flex items-center justify-between gap-2">
                    <div className="truncate text-sm">
                      {a.summary ?? a.kind}
                    </div>
                    <Pill tone="default">{a.kind}</Pill>
                  </div>
                  <div className="mt-0.5 text-[11px] text-muted">
                    {formatDate(a.occurred_at)}
                    {a.author ? ` · ${a.author}` : ""}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Source metadata">
          <dl className="grid grid-cols-[160px,1fr] gap-y-2 text-sm">
            <dt className="text-muted">Source</dt>
            <dd>
              <SourceBadge source="investor_engine" />
            </dd>
            <dt className="text-muted">external_id</dt>
            <dd className="break-all font-mono text-xs">{n.external_id}</dd>
            <dt className="text-muted">engine_updated_at</dt>
            <dd>{formatDate(n.engine_updated_at)}</dd>
            <dt className="text-muted">Website</dt>
            <dd>
              {n.website ? (
                <a
                  className="hover:underline"
                  href={n.website}
                  target="_blank"
                  rel="noreferrer"
                >
                  {n.website}
                </a>
              ) : (
                "—"
              )}
            </dd>
            <dt className="text-muted">Location</dt>
            <dd>{n.location ?? "—"}</dd>
            <dt className="text-muted">Stage focus</dt>
            <dd>{n.stage_focus ?? "—"}</dd>
          </dl>
        </Panel>
      </div>

      <EngineWritesPanel externalId={externalId} />

      {draft && (
        <DraftReviewModal
          communication={draft}
          onClose={() => setDraft(null)}
        />
      )}
    </div>
  );
}
