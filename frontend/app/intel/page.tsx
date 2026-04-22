"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Empty, Panel, Pill } from "@/components/ui";
import type {
  IntelByCategory,
  IntelByRegion,
  IntelCategory,
  IntelItemRead,
  IntelTopSignals,
} from "@/types/api";

type ViewMode = "signals" | "category" | "region" | "watchlist";

const CATEGORY_LABEL: Record<IntelCategory, string> = {
  vc_funding: "VC Funding",
  defense_tech: "Defense Tech",
  space_systems: "Space Systems",
  aerospace_manufacturing: "Aerospace Manufacturing",
  supply_chain: "Supply Chain",
  policy_procurement: "Policy & Procurement",
  competitor_move: "Competitor Move",
  partner_signal: "Partner Signal",
  supplier_signal: "Supplier Signal",
  uncategorized: "Uncategorized",
};

export default function IntelPage() {
  const qc = useQueryClient();
  const [view, setView] = useState<ViewMode>("signals");
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const summary = useQuery({
    queryKey: ["intel-summary"],
    queryFn: api.intelSummary,
  });
  const top = useQuery<IntelTopSignals>({
    queryKey: ["intel-top"],
    queryFn: () => api.intelTopSignals(20),
  });
  const byCategory = useQuery<IntelByCategory>({
    queryKey: ["intel-by-category"],
    queryFn: () => api.intelByCategory(5),
    enabled: view === "category",
  });
  const byRegion = useQuery<IntelByRegion>({
    queryKey: ["intel-by-region"],
    queryFn: () => api.intelByRegion(5),
    enabled: view === "region",
  });
  const watchlist = useQuery<IntelItemRead[]>({
    queryKey: ["intel-watchlist"],
    queryFn: () => api.listIntel({ tag: "watchlist", limit: 25 }),
    enabled: view === "watchlist",
  });
  const selected = useQuery<IntelItemRead>({
    queryKey: ["intel-item", selectedId],
    queryFn: () => api.getIntel(selectedId as number),
    enabled: selectedId != null,
  });

  const ingest = useMutation({
    mutationFn: () => api.triggerIntelIngest("ui"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["intel-summary"] });
      qc.invalidateQueries({ queryKey: ["intel-top"] });
      qc.invalidateQueries({ queryKey: ["intel-by-category"] });
      qc.invalidateQueries({ queryKey: ["intel-by-region"] });
      qc.invalidateQueries({ queryKey: ["intel-watchlist"] });
    },
  });

  const ack = useMutation({
    mutationFn: (id: number) => api.intelAckAction(id, "ui"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["intel-item"] });
      qc.invalidateQueries({ queryKey: ["intel-top"] });
    },
  });
  const resolve = useMutation({
    mutationFn: (id: number) => api.intelResolveAction(id, "ui"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["intel-item"] });
      qc.invalidateQueries({ queryKey: ["intel-top"] });
    },
  });
  const dismiss = useMutation({
    mutationFn: (id: number) => api.intelDismissAction(id, "ui"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["intel-item"] });
      qc.invalidateQueries({ queryKey: ["intel-top"] });
    },
  });

  const totalCount = summary.data?.total ?? 0;
  const topCount = summary.data?.top_signals ?? 0;

  return (
    <div className="space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold">Intelligence</h1>
            <Pill tone="accent">mode · intel</Pill>
          </div>
          <p className="mt-1 text-sm text-muted">
            External news and market signals — venture activity, defense
            moves, supply chain shocks — classified for Asgard relevance.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="rounded border border-border bg-bg/40 px-3 py-1.5 text-xs">
            <span className="text-muted">total</span>
            <span className="ml-2 font-mono tabular-nums">{totalCount}</span>
            <span className="mx-2 text-muted">·</span>
            <span className="text-muted">top</span>
            <span className="ml-2 font-mono tabular-nums">{topCount}</span>
          </div>
          <button
            onClick={() => ingest.mutate()}
            disabled={ingest.isPending}
            className="rounded border border-border bg-panel px-3 py-1.5 font-mono text-xs uppercase tracking-wider hover:border-accent hover:text-accent disabled:opacity-50"
          >
            {ingest.isPending ? "ingesting…" : "run ingestion"}
          </button>
        </div>
      </header>

      {ingest.data && (
        <div className="rounded border border-accent/40 bg-accent/5 px-3 py-2 text-xs text-accent">
          Ingested {ingest.data.total_items_seen} item(s) · created{" "}
          {ingest.data.created} · updated {ingest.data.updated} · skipped{" "}
          {ingest.data.skipped}
        </div>
      )}

      <div className="flex items-center gap-1 border-b border-border">
        {(["signals", "category", "region", "watchlist"] as ViewMode[]).map(
          (v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={
                "px-3 py-2 font-mono text-xs uppercase tracking-wider " +
                (view === v
                  ? "border-b-2 border-accent text-accent"
                  : "text-muted hover:text-ink")
              }
            >
              {v === "signals"
                ? "Top signals"
                : v === "category"
                ? "By category"
                : v === "region"
                ? "By region"
                : "Watchlist"}
            </button>
          ),
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_360px]">
        {/* Main feed */}
        <div className="space-y-4">
          {view === "signals" && (
            <Panel title={`Top strategic signals · ${top.data?.total ?? 0}`}>
              {top.isLoading ? (
                <Empty>Loading…</Empty>
              ) : !top.data || top.data.items.length === 0 ? (
                <Empty>
                  No signals yet. Hit <b>run ingestion</b> to seed data.
                </Empty>
              ) : (
                <ul className="divide-y divide-border">
                  {top.data.items.map((it) => (
                    <IntelRow
                      key={it.id}
                      item={it}
                      active={selectedId === it.id}
                      onSelect={() => setSelectedId(it.id)}
                    />
                  ))}
                </ul>
              )}
            </Panel>
          )}

          {view === "category" && (
            <div className="space-y-4">
              {byCategory.isLoading && <Empty>Loading categories…</Empty>}
              {byCategory.data?.categories.map((b) => (
                <Panel
                  key={b.category}
                  title={`${CATEGORY_LABEL[b.category]} · ${b.count}`}
                >
                  {b.items.length === 0 ? (
                    <Empty>No items.</Empty>
                  ) : (
                    <ul className="divide-y divide-border">
                      {b.items.map((it) => (
                        <IntelRow
                          key={it.id}
                          item={it}
                          active={selectedId === it.id}
                          onSelect={() => setSelectedId(it.id)}
                        />
                      ))}
                    </ul>
                  )}
                </Panel>
              ))}
            </div>
          )}

          {view === "region" && (
            <div className="space-y-4">
              {byRegion.isLoading && <Empty>Loading regions…</Empty>}
              {byRegion.data?.regions.map((b) => (
                <Panel key={b.region} title={`${b.region} · ${b.count}`}>
                  {b.items.length === 0 ? (
                    <Empty>No items.</Empty>
                  ) : (
                    <ul className="divide-y divide-border">
                      {b.items.map((it) => (
                        <IntelRow
                          key={it.id}
                          item={it}
                          active={selectedId === it.id}
                          onSelect={() => setSelectedId(it.id)}
                        />
                      ))}
                    </ul>
                  )}
                </Panel>
              ))}
            </div>
          )}

          {view === "watchlist" && (
            <Panel title={`Watchlist · ${watchlist.data?.length ?? 0}`}>
              {watchlist.isLoading ? (
                <Empty>Loading…</Empty>
              ) : !watchlist.data || watchlist.data.length === 0 ? (
                <Empty>No watchlist hits.</Empty>
              ) : (
                <ul className="divide-y divide-border">
                  {watchlist.data.map((it) => (
                    <IntelRow
                      key={it.id}
                      item={it}
                      active={selectedId === it.id}
                      onSelect={() => setSelectedId(it.id)}
                    />
                  ))}
                </ul>
              )}
            </Panel>
          )}
        </div>

        {/* Right context panel */}
        <aside className="space-y-4 lg:sticky lg:top-4 lg:self-start">
          <Panel title="Signal detail">
            {!selectedId ? (
              <Empty>Select a signal to load its detail.</Empty>
            ) : selected.isLoading ? (
              <Empty>Loading…</Empty>
            ) : !selected.data ? (
              <Empty>Not found.</Empty>
            ) : (
              <IntelDetail
                item={selected.data}
                onAck={(id) => ack.mutate(id)}
                onResolve={(id) => resolve.mutate(id)}
                onDismiss={(id) => dismiss.mutate(id)}
              />
            )}
          </Panel>

          <Panel title="Recommended queue actions">
            <RecommendedQueue
              items={top.data?.items ?? []}
              onSelect={setSelectedId}
            />
          </Panel>
        </aside>
      </div>
    </div>
  );
}

function IntelRow({
  item,
  active,
  onSelect,
}: {
  item: IntelItemRead;
  active: boolean;
  onSelect: () => void;
}) {
  const tone = scoreTone(item.strategic_relevance_score);
  return (
    <li>
      <button
        onClick={onSelect}
        className={
          "flex w-full items-start justify-between gap-3 px-2 py-2 text-left transition-colors " +
          (active ? "bg-accent/10" : "hover:bg-border/30")
        }
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <Pill tone={tone}>
              s{item.strategic_relevance_score}
            </Pill>
            <Pill tone="default">u{item.urgency_score}</Pill>
            <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
              {CATEGORY_LABEL[item.category]}
            </span>
            {item.region && (
              <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
                · {item.region}
              </span>
            )}
          </div>
          <div className="mt-1 truncate text-sm text-ink">{item.title}</div>
          {item.summary && (
            <div className="mt-0.5 line-clamp-2 text-xs text-muted">
              {item.summary}
            </div>
          )}
          <div className="mt-1 flex flex-wrap gap-1">
            {item.tags.slice(0, 4).map((t) => (
              <span
                key={t.id}
                className="rounded border border-border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-muted"
              >
                {t.tag}
              </span>
            ))}
          </div>
        </div>
        <div className="shrink-0 text-right font-mono text-[10px] text-muted">
          {item.published_at
            ? new Date(item.published_at).toISOString().slice(0, 10)
            : "—"}
        </div>
      </button>
    </li>
  );
}

function IntelDetail({
  item,
  onAck,
  onResolve,
  onDismiss,
}: {
  item: IntelItemRead;
  onAck: (actionId: number) => void;
  onResolve: (actionId: number) => void;
  onDismiss: (actionId: number) => void;
}) {
  return (
    <div className="space-y-3 text-sm">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <Pill tone={scoreTone(item.strategic_relevance_score)}>
            s{item.strategic_relevance_score}
          </Pill>
          <Pill tone="warn">u{item.urgency_score}</Pill>
          <Pill tone="default">c{item.confidence_score}</Pill>
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
            {CATEGORY_LABEL[item.category]}
          </span>
        </div>
        <h3 className="mt-2 text-sm font-semibold">{item.title}</h3>
        <div className="mt-1 font-mono text-[10px] uppercase tracking-widest text-muted">
          {item.source} · {item.region ?? "—"}
        </div>
        {item.url && (
          <a
            href={item.url}
            target="_blank"
            rel="noreferrer"
            className="mt-1 block truncate text-xs text-accent hover:underline"
          >
            {item.url}
          </a>
        )}
      </div>

      {item.summary && (
        <p className="whitespace-pre-wrap text-xs text-muted">{item.summary}</p>
      )}

      {item.entities.length > 0 && (
        <div>
          <div className="mb-1 font-mono text-[10px] uppercase tracking-widest text-muted">
            Entities
          </div>
          <ul className="space-y-1 text-xs">
            {item.entities.map((e) => (
              <li key={e.id} className="flex items-center justify-between">
                <span>
                  <span className="text-ink">{e.entity_name}</span>
                  <span className="ml-2 font-mono text-[10px] uppercase tracking-wider text-muted">
                    {e.entity_type}
                  </span>
                </span>
                {e.role && (
                  <span className="font-mono text-[10px] uppercase tracking-wider text-muted">
                    {e.role}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {item.tags.length > 0 && (
        <div>
          <div className="mb-1 font-mono text-[10px] uppercase tracking-widest text-muted">
            Tags
          </div>
          <div className="flex flex-wrap gap-1">
            {item.tags.map((t) => (
              <span
                key={t.id}
                className="rounded border border-border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-muted"
              >
                {t.tag}
              </span>
            ))}
          </div>
        </div>
      )}

      {item.actions.length > 0 && (
        <div>
          <div className="mb-1 font-mono text-[10px] uppercase tracking-widest text-muted">
            Recommended actions
          </div>
          <ul className="space-y-2">
            {item.actions.map((a) => (
              <li
                key={a.id}
                className="rounded border border-border bg-bg/30 p-2"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] uppercase tracking-wider text-accent">
                    {a.action_type}
                  </span>
                  <Pill tone={a.status === "pending" ? "warn" : "ok"}>
                    {a.status}
                  </Pill>
                </div>
                <p className="mt-1 text-xs text-muted">{a.recommended_action}</p>
                {a.status === "pending" && (
                  <div className="mt-2 flex gap-1">
                    <button
                      onClick={() => onAck(a.id)}
                      className="rounded border border-border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider hover:border-accent hover:text-accent"
                    >
                      ack
                    </button>
                    <button
                      onClick={() => onResolve(a.id)}
                      className="rounded border border-border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider hover:border-ok hover:text-ok"
                    >
                      resolve
                    </button>
                    <button
                      onClick={() => onDismiss(a.id)}
                      className="rounded border border-border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider hover:border-danger hover:text-danger"
                    >
                      dismiss
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function RecommendedQueue({
  items,
  onSelect,
}: {
  items: IntelItemRead[];
  onSelect: (id: number) => void;
}) {
  const queueRows = useMemo(() => {
    const rows: Array<{
      intelId: number;
      title: string;
      action: string;
      score: number;
    }> = [];
    for (const it of items) {
      for (const a of it.actions) {
        if (a.status !== "pending") continue;
        rows.push({
          intelId: it.id,
          title: it.title,
          action: a.recommended_action,
          score: it.strategic_relevance_score,
        });
      }
    }
    rows.sort((a, b) => b.score - a.score);
    return rows.slice(0, 10);
  }, [items]);

  if (queueRows.length === 0) {
    return <Empty>No pending actions in queue.</Empty>;
  }
  return (
    <ul className="space-y-1.5 text-xs">
      {queueRows.map((r, idx) => (
        <li key={`${r.intelId}.${idx}`}>
          <button
            onClick={() => onSelect(r.intelId)}
            className="flex w-full items-start gap-2 rounded border border-border bg-bg/30 p-2 text-left hover:border-accent hover:text-accent"
          >
            <Pill tone={scoreTone(r.score)}>s{r.score}</Pill>
            <div className="min-w-0 flex-1">
              <div className="truncate text-ink">{r.title}</div>
              <div className="truncate text-muted">{r.action}</div>
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
}

function scoreTone(
  score: number,
): "default" | "accent" | "warn" | "danger" | "ok" {
  if (score >= 75) return "danger";
  if (score >= 55) return "warn";
  if (score >= 35) return "accent";
  return "default";
}
