"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import Link from "next/link";
import {
  Empty,
  Panel,
  Pill,
  SourceBadge,
  Stat,
  formatDate,
  relative,
} from "@/components/ui";
import { OpportunityList } from "@/components/outputs/ranked-output";
import { ActionRow, AlertRow } from "@/components/executive";

export default function DashboardPage() {
  const pipeline = useQuery({
    queryKey: ["pipeline-summary"],
    queryFn: api.pipelineSummary,
  });
  const overdue = useQuery({
    queryKey: ["overdue"],
    queryFn: api.overdue,
  });
  const stale = useQuery({
    queryKey: ["stale"],
    queryFn: () => api.stale(21),
  });
  const approvals = useQuery({
    queryKey: ["approvals-pending"],
    queryFn: api.pendingApprovals,
  });
  const activity = useQuery({
    queryKey: ["activity"],
    queryFn: () => api.activity(15),
  });
  const engineSummary = useQuery({
    queryKey: ["engine-summary"],
    queryFn: api.engineDashboardSummary,
  });
  const engineDue = useQuery({
    queryKey: ["engine-follow-ups-due"],
    queryFn: () => api.engineFollowUpsDue(10),
  });
  const marketSummary = useQuery({
    queryKey: ["market-summary"],
    queryFn: api.marketDashboardSummary,
  });
  const marketOpps = useQuery({
    queryKey: ["market-active-opps"],
    queryFn: () => api.listActiveMarketOpportunities(8),
  });
  const marketFollowUps = useQuery({
    queryKey: ["market-follow-ups"],
    queryFn: () => api.listMarketFollowUps(8),
  });
  const programPipeline = useQuery({
    queryKey: ["program-pipeline"],
    queryFn: api.programPipelineSummary,
  });
  const programsActive = useQuery({
    queryKey: ["programs-active-dash"],
    queryFn: () => api.listActivePrograms(8),
  });
  const supplierSummary = useQuery({
    queryKey: ["supplier-onboarding-dash"],
    queryFn: api.onboardingSummary,
  });
  const qualifiedSuppliers = useQuery({
    queryKey: ["suppliers-qualified-dash"],
    queryFn: () => api.listQualifiedSuppliers(8),
  });
  const suppliersByCapability = useQuery({
    queryKey: ["suppliers-by-capability-dash"],
    queryFn: api.suppliersByCapability,
  });
  const execBriefing = useQuery({
    queryKey: ["exec-briefing-dash"],
    queryFn: api.executiveBriefing,
  });

  const summary = pipeline.data;
  const engineCounts = engineSummary.data ?? {};
  const engineStageEntries = Object.entries(engineCounts)
    .filter(([k]) => k.startsWith("stage."))
    .map(([k, v]) => [k.replace("stage.", ""), v] as const);
  const engineFollowUpEntries = Object.entries(engineCounts)
    .filter(([k]) => k.startsWith("follow_up."))
    .map(([k, v]) => [k.replace("follow_up.", ""), v] as const);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-xl font-semibold">Dashboard</h1>
        <p className="mt-1 text-sm text-muted">
          {summary?.narrative ?? "Loading pipeline state…"}
        </p>
      </header>

      {execBriefing.data && (
        <div className="rounded-lg border border-border bg-panel">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <div className="flex items-center gap-2">
              <h2 className="font-mono text-xs uppercase tracking-widest text-muted">
                Executive briefing
              </h2>
              <span className="text-xs text-ink/80">
                {execBriefing.data.headline}
              </span>
            </div>
            <Link
              href="/executive"
              className="font-mono text-[11px] uppercase tracking-widest text-muted hover:text-ink"
            >
              Open →
            </Link>
          </div>
          <div className="grid grid-cols-1 gap-6 p-4 lg:grid-cols-2">
            <div>
              <div className="mb-2 font-mono text-[10px] uppercase tracking-widest text-muted">
                Top actions
              </div>
              {execBriefing.data.top_actions.length === 0 ? (
                <Empty>Queue is clear.</Empty>
              ) : (
                <ul className="divide-y divide-border">
                  {execBriefing.data.top_actions.slice(0, 5).map((a) => (
                    <ActionRow key={a.id} a={a} />
                  ))}
                </ul>
              )}
            </div>
            <div>
              <div className="mb-2 font-mono text-[10px] uppercase tracking-widest text-muted">
                Top risks
              </div>
              {execBriefing.data.top_risks.length === 0 ? (
                <Empty>No risks flagged.</Empty>
              ) : (
                <ul className="divide-y divide-border">
                  {execBriefing.data.top_risks.slice(0, 5).map((a) => (
                    <AlertRow key={a.id} a={a} />
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Stat label="Active" value={summary?.total_active ?? "—"} />
        <Stat label="Overdue" value={summary?.overdue_follow_up_count ?? "—"} />
        <Stat label="Stale" value={summary?.stale_count ?? "—"} />
        <Stat
          label="Missing next step"
          value={summary?.missing_next_step_count ?? "—"}
        />
        <Stat
          label="Pending approvals"
          value={approvals.data?.length ?? "—"}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Panel title="Pipeline by stage">
          {pipeline.isLoading ? (
            <Empty>Loading…</Empty>
          ) : !summary || summary.stage_counts.length === 0 ? (
            <Empty>No active opportunities.</Empty>
          ) : (
            <div className="grid grid-cols-3 gap-2">
              {summary.stage_counts.map((s) => (
                <div
                  key={s.stage}
                  className="rounded border border-border bg-bg/40 px-3 py-2"
                >
                  <div className="font-mono text-[10px] uppercase tracking-widest text-muted">
                    {s.stage}
                  </div>
                  <div className="text-xl tabular-nums">{s.count}</div>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Top priority">
          {pipeline.isLoading ? (
            <Empty>Loading…</Empty>
          ) : !summary || summary.top_priority.length === 0 ? (
            <Empty>No priorities.</Empty>
          ) : (
            <OpportunityList list={summary.top_priority.slice(0, 6)} />
          )}
        </Panel>

        <Panel title="Overdue follow-ups">
          {overdue.isLoading ? (
            <Empty>Loading…</Empty>
          ) : !overdue.data || overdue.data.length === 0 ? (
            <Empty>Nothing overdue.</Empty>
          ) : (
            <ul className="divide-y divide-border">
              {overdue.data.map((o) => (
                <li
                  key={o.id}
                  className="flex items-start justify-between py-2"
                >
                  <div className="min-w-0">
                    <div className="truncate font-medium">
                      {o.firm_name ?? `opportunity #${o.id}`}
                    </div>
                    <div className="text-xs text-muted">
                      due {formatDate(o.next_step_due_at)}
                    </div>
                  </div>
                  <Pill tone="danger">overdue</Pill>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Stale opportunities">
          {stale.isLoading ? (
            <Empty>Loading…</Empty>
          ) : !stale.data || stale.data.length === 0 ? (
            <Empty>No stale opportunities.</Empty>
          ) : (
            <ul className="divide-y divide-border">
              {stale.data.map((o) => (
                <li
                  key={o.id}
                  className="flex items-start justify-between py-2"
                >
                  <div className="min-w-0">
                    <div className="truncate font-medium">
                      {o.firm_name ?? `opportunity #${o.id}`}
                    </div>
                    <div className="text-xs text-muted">
                      last {relative(o.last_interaction_at)}
                    </div>
                  </div>
                  <Pill tone="warn">stale</Pill>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Pending approvals">
          {approvals.isLoading ? (
            <Empty>Loading…</Empty>
          ) : !approvals.data || approvals.data.length === 0 ? (
            <Empty>No pending approvals.</Empty>
          ) : (
            <ul className="divide-y divide-border">
              {approvals.data.map((a) => (
                <li
                  key={a.id}
                  className="flex items-center justify-between py-2"
                >
                  <div className="min-w-0">
                    <div className="truncate">
                      {a.action} · {a.entity_type} #{a.entity_id}
                    </div>
                    <div className="text-xs text-muted">
                      requested by {a.requested_by ?? "unknown"} ·{" "}
                      {relative(a.created_at)}
                    </div>
                  </div>
                  <Pill tone="warn">{a.status}</Pill>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Recent activity (Bifrost)">
          {activity.isLoading ? (
            <Empty>Loading…</Empty>
          ) : !activity.data || activity.data.length === 0 ? (
            <Empty>No recent activity.</Empty>
          ) : (
            <ul className="divide-y divide-border">
              {activity.data.map((e) => {
                const summary =
                  (e.payload as { summary?: string } | null)?.summary ??
                  e.event_type;
                return (
                  <li key={e.id} className="py-2">
                    <div className="truncate text-sm">{summary}</div>
                    <div className="mt-0.5 text-[11px] text-muted">
                      {e.event_type} · {relative(e.created_at)}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>
      </div>

      <div className="pt-4">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="text-base font-semibold">Investor Engine</h2>
            <SourceBadge source="investor_engine" />
          </div>
          <Link
            href="/engine"
            className="font-mono text-[11px] uppercase tracking-widest text-muted hover:text-ink"
          >
            Open list →
          </Link>
        </div>
        <p className="mb-3 text-xs text-muted">
          External system · read-only snapshot. Records here are owned by
          the investor engine, not by Bifrost.
        </p>

        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat
            label="Engine records"
            value={engineCounts["total"] ?? "—"}
          />
          <Stat
            label="Follow-ups due"
            value={engineDue.data?.length ?? "—"}
          />
          <Stat
            label="Stages tracked"
            value={engineStageEntries.length || "—"}
          />
          <Stat
            label="Follow-up states"
            value={engineFollowUpEntries.length || "—"}
          />
        </div>

        <div className="mt-3 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Panel
            title="Engine · counts by stage"
            right={<SourceBadge source="investor_engine" />}
          >
            {engineSummary.isLoading ? (
              <Empty>Loading…</Empty>
            ) : engineStageEntries.length === 0 ? (
              <Empty>No engine records synced.</Empty>
            ) : (
              <div className="grid grid-cols-3 gap-2">
                {engineStageEntries.map(([stage, count]) => (
                  <div
                    key={stage}
                    className="rounded border border-border bg-bg/40 px-3 py-2"
                  >
                    <div className="font-mono text-[10px] uppercase tracking-widest text-muted">
                      {stage}
                    </div>
                    <div className="text-xl tabular-nums">{count}</div>
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <Panel
            title="Engine · follow-up status"
            right={<SourceBadge source="investor_engine" />}
          >
            {engineSummary.isLoading ? (
              <Empty>Loading…</Empty>
            ) : engineFollowUpEntries.length === 0 ? (
              <Empty>No follow-up data.</Empty>
            ) : (
              <ul className="divide-y divide-border">
                {engineFollowUpEntries.map(([status, count]) => (
                  <li
                    key={status}
                    className="flex items-center justify-between py-2"
                  >
                    <span className="font-mono text-xs uppercase tracking-widest text-muted">
                      {status}
                    </span>
                    <span className="tabular-nums">{count}</span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel
            title="Engine · follow-ups due"
            right={<SourceBadge source="investor_engine" />}
          >
            {engineDue.isLoading ? (
              <Empty>Loading…</Empty>
            ) : !engineDue.data || engineDue.data.length === 0 ? (
              <Empty>No follow-ups due.</Empty>
            ) : (
              <ul className="divide-y divide-border">
                {engineDue.data.map((n) => (
                  <li
                    key={n.external_id}
                    className="flex items-start justify-between py-2"
                  >
                    <div className="min-w-0">
                      <Link
                        href={`/engine/${encodeURIComponent(n.external_id)}`}
                        className="truncate font-medium hover:underline"
                      >
                        {n.firm_name}
                      </Link>
                      <div className="text-xs text-muted">
                        due {formatDate(n.next_follow_up_at)}
                        {n.owner ? ` · ${n.owner}` : ""}
                      </div>
                    </div>
                    <Pill tone="warn">{n.follow_up_status ?? "due"}</Pill>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel
            title="Engine · high-priority"
            right={<SourceBadge source="investor_engine" />}
          >
            {engineDue.isLoading ? (
              <Empty>Loading…</Empty>
            ) : !engineDue.data || engineDue.data.length === 0 ? (
              <Empty>Nothing flagged.</Empty>
            ) : (
              <ul className="divide-y divide-border">
                {engineDue.data
                  .slice()
                  .sort(
                    (a, b) =>
                      (b.probability_score ?? 0) -
                      (a.probability_score ?? 0),
                  )
                  .slice(0, 6)
                  .map((n) => (
                    <li
                      key={n.external_id}
                      className="flex items-start justify-between py-2"
                    >
                      <div className="min-w-0">
                        <Link
                          href={`/engine/${encodeURIComponent(n.external_id)}`}
                          className="truncate font-medium hover:underline"
                        >
                          {n.firm_name}
                        </Link>
                        <div className="text-xs text-muted">
                          {n.stage ?? "—"} ·{" "}
                          {relative(n.last_touch_at)} last touch
                        </div>
                      </div>
                      <Pill tone="accent">
                        p{n.probability_score ?? "?"}
                      </Pill>
                    </li>
                  ))}
              </ul>
            )}
          </Panel>
        </div>
      </div>

      <div className="pt-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-base font-semibold">Market</h2>
          <Link
            href="/market"
            className="font-mono text-[11px] uppercase tracking-widest text-muted hover:text-ink"
          >
            Open list →
          </Link>
        </div>
        <p className="mb-3 text-xs text-muted">
          Target accounts, outreach campaigns, and market opportunities.
        </p>

        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat
            label="Total accounts"
            value={marketSummary.data?.total_accounts ?? "—"}
          />
          <Stat
            label="Active campaigns"
            value={marketSummary.data?.active_campaigns ?? "—"}
          />
          <Stat
            label="Active opportunities"
            value={marketSummary.data?.active_opportunities ?? "—"}
          />
          <Stat
            label="Accounts needing follow-up"
            value={marketSummary.data?.accounts_needing_follow_up ?? "—"}
          />
        </div>

        <div className="mt-3 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Panel title="Active market opportunities">
            {marketOpps.isLoading ? (
              <Empty>Loading…</Empty>
            ) : !marketOpps.data || marketOpps.data.length === 0 ? (
              <Empty>No active market opportunities.</Empty>
            ) : (
              <ul className="divide-y divide-border">
                {marketOpps.data.map((o) => (
                  <li key={o.id} className="flex items-start justify-between py-2">
                    <div className="min-w-0">
                      <div className="truncate font-medium">{o.name}</div>
                      <div className="text-xs text-muted">
                        {o.account_name ?? `account #${o.account_id}`}
                        {o.next_step_due_at
                          ? ` · due ${formatDate(o.next_step_due_at)}`
                          : ""}
                      </div>
                    </div>
                    <Pill tone="accent">{o.stage}</Pill>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel title="Accounts needing follow-up">
            {marketFollowUps.isLoading ? (
              <Empty>Loading…</Empty>
            ) : !marketFollowUps.data || marketFollowUps.data.length === 0 ? (
              <Empty>No follow-ups due.</Empty>
            ) : (
              <ul className="divide-y divide-border">
                {marketFollowUps.data.map((l) => (
                  <li key={l.id} className="flex items-start justify-between py-2">
                    <div className="min-w-0">
                      <div className="truncate font-medium">
                        {l.account_name ?? `account #${l.account_id}`}
                      </div>
                      <div className="text-xs text-muted">
                        {l.campaign_name ?? `campaign #${l.campaign_id}`} · due{" "}
                        {formatDate(l.next_follow_up_at)}
                      </div>
                    </div>
                    <Pill tone="warn">{l.status}</Pill>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </div>

      <div className="pt-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-base font-semibold">Programs</h2>
          <Link
            href="/programs"
            className="font-mono text-[11px] uppercase tracking-widest text-muted hover:text-ink"
          >
            Open list →
          </Link>
        </div>
        <p className="mb-3 text-xs text-muted">
          Execution layer · contracts, pursuits, partnerships.
        </p>

        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat
            label="Active programs"
            value={programPipeline.data?.active_count ?? "—"}
          />
          <Stat
            label="High-value"
            value={programPipeline.data?.high_value_count ?? "—"}
          />
          <Stat
            label="Overdue"
            value={programPipeline.data?.overdue_count ?? "—"}
          />
          <Stat
            label="Won"
            value={programPipeline.data?.won_count ?? "—"}
          />
        </div>

        <div className="mt-3 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Panel title="Active programs">
            {programsActive.isLoading ? (
              <Empty>Loading…</Empty>
            ) : !programsActive.data || programsActive.data.length === 0 ? (
              <Empty>No active programs.</Empty>
            ) : (
              <ul className="divide-y divide-border">
                {programsActive.data.map((p) => (
                  <li
                    key={p.id}
                    className="flex items-start justify-between py-2"
                  >
                    <div className="min-w-0">
                      <div className="truncate font-medium">{p.name}</div>
                      <div className="text-xs text-muted">
                        {p.account_name ?? `account #${p.account_id}`}
                        {p.owner ? ` · ${p.owner}` : ""}
                      </div>
                    </div>
                    <Pill tone="accent">{p.stage}</Pill>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel title="Pipeline by stage">
            {programPipeline.isLoading ? (
              <Empty>Loading…</Empty>
            ) : !programPipeline.data ||
              programPipeline.data.stage_counts.length === 0 ? (
              <Empty>No programs yet.</Empty>
            ) : (
              <div className="grid grid-cols-3 gap-2">
                {programPipeline.data.stage_counts.map((s) => (
                  <div
                    key={s.stage}
                    className="rounded border border-border bg-bg/40 px-3 py-2"
                  >
                    <div className="font-mono text-[10px] uppercase tracking-widest text-muted">
                      {s.stage}
                    </div>
                    <div className="text-xl tabular-nums">{s.count}</div>
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <Panel title="High-value programs">
            {programPipeline.isLoading ? (
              <Empty>Loading…</Empty>
            ) : !programPipeline.data ||
              programPipeline.data.high_value.length === 0 ? (
              <Empty>Nothing flagged.</Empty>
            ) : (
              <ul className="divide-y divide-border">
                {programPipeline.data.high_value.map((p) => (
                  <li
                    key={p.id}
                    className="flex items-start justify-between py-2"
                  >
                    <div className="min-w-0">
                      <div className="truncate font-medium">{p.name}</div>
                      <div className="text-xs text-muted">
                        {p.account_name ?? `account #${p.account_id}`}
                      </div>
                    </div>
                    <span className="text-[11px] text-muted tabular-nums">
                      {p.estimated_value != null
                        ? `$${(p.estimated_value / 1_000_000).toFixed(1)}M`
                        : "—"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel title="Overdue programs">
            {programPipeline.isLoading ? (
              <Empty>Loading…</Empty>
            ) : !programPipeline.data ||
              programPipeline.data.overdue.length === 0 ? (
              <Empty>Nothing overdue.</Empty>
            ) : (
              <ul className="divide-y divide-border">
                {programPipeline.data.overdue.map((p) => (
                  <li
                    key={p.id}
                    className="flex items-start justify-between py-2"
                  >
                    <div className="min-w-0">
                      <div className="truncate font-medium">{p.name}</div>
                      <div className="text-xs text-muted">
                        due {formatDate(p.next_step_due_at)}
                      </div>
                    </div>
                    <Pill tone="danger">overdue</Pill>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </div>

      <div className="pt-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-base font-semibold">Suppliers</h2>
          <Link
            href="/suppliers"
            className="font-mono text-[11px] uppercase tracking-widest text-muted hover:text-ink"
          >
            Open list →
          </Link>
        </div>
        <p className="mb-3 text-xs text-muted">
          Manufacturing network · capabilities, certifications, onboarding.
        </p>

        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat
            label="Total suppliers"
            value={supplierSummary.data?.total ?? "—"}
          />
          <Stat
            label="Qualified"
            value={supplierSummary.data?.qualified ?? "—"}
          />
          <Stat
            label="Onboarded"
            value={supplierSummary.data?.onboarded ?? "—"}
          />
          <Stat
            label="On active programs"
            value={
              supplierSummary.data?.active_program_supplier_count ?? "—"
            }
          />
        </div>

        <div className="mt-3 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Panel title="Onboarding pipeline">
            {supplierSummary.isLoading ? (
              <Empty>Loading…</Empty>
            ) : !supplierSummary.data ||
              Object.keys(supplierSummary.data.by_status).length === 0 ? (
              <Empty>No suppliers yet.</Empty>
            ) : (
              <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
                {Object.entries(supplierSummary.data.by_status).map(
                  ([k, v]) => (
                    <div
                      key={k}
                      className="rounded border border-border bg-bg/40 px-3 py-2"
                    >
                      <div className="font-mono text-[10px] uppercase tracking-widest text-muted">
                        {k}
                      </div>
                      <div className="text-lg tabular-nums">{v}</div>
                    </div>
                  ),
                )}
              </div>
            )}
          </Panel>

          <Panel title="Qualified suppliers">
            {qualifiedSuppliers.isLoading ? (
              <Empty>Loading…</Empty>
            ) : !qualifiedSuppliers.data ||
              qualifiedSuppliers.data.length === 0 ? (
              <Empty>No qualified suppliers yet.</Empty>
            ) : (
              <ul className="divide-y divide-border">
                {qualifiedSuppliers.data.map((s) => (
                  <li
                    key={s.id}
                    className="flex items-center justify-between py-2"
                  >
                    <div className="min-w-0">
                      <div className="truncate font-medium">{s.name}</div>
                      <div className="text-xs text-muted">
                        {[s.type, s.region].filter(Boolean).join(" · ") || "—"}
                      </div>
                    </div>
                    <Pill
                      tone={
                        s.onboarding_status === "onboarded" ? "ok" : "accent"
                      }
                    >
                      {s.onboarding_status}
                    </Pill>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel title="By capability">
            {suppliersByCapability.isLoading ? (
              <Empty>Loading…</Empty>
            ) : !suppliersByCapability.data ||
              Object.keys(suppliersByCapability.data).length === 0 ? (
              <Empty>No capabilities recorded.</Empty>
            ) : (
              <ul className="divide-y divide-border">
                {Object.entries(suppliersByCapability.data).map(
                  ([cap, rows]) => (
                    <li
                      key={cap}
                      className="flex items-center justify-between py-2"
                    >
                      <span className="font-mono text-xs uppercase tracking-widest text-muted">
                        {cap}
                      </span>
                      <span className="tabular-nums">{rows.length}</span>
                    </li>
                  ),
                )}
              </ul>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
