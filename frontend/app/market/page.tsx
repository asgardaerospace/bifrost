"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Empty, Panel, Pill, Stat, formatDate } from "@/components/ui";

export default function MarketPage() {
  const summary = useQuery({
    queryKey: ["market-summary"],
    queryFn: api.marketDashboardSummary,
  });
  const accounts = useQuery({
    queryKey: ["market-accounts"],
    queryFn: () => api.listAccounts({ limit: 100 }),
  });
  const campaigns = useQuery({
    queryKey: ["market-campaigns"],
    queryFn: () => api.listCampaigns({ limit: 100 }),
  });
  const opps = useQuery({
    queryKey: ["market-opps"],
    queryFn: () => api.listMarketOpportunities({ limit: 100 }),
  });
  const followUps = useQuery({
    queryKey: ["market-follow-ups-all"],
    queryFn: () => api.listMarketFollowUps(100),
  });

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-xl font-semibold">Market</h1>
        <p className="mt-1 text-sm text-muted">
          Target accounts, outreach campaigns, and market opportunities.
        </p>
      </header>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Total accounts" value={summary.data?.total_accounts ?? "—"} />
        <Stat label="Active campaigns" value={summary.data?.active_campaigns ?? "—"} />
        <Stat
          label="Active opportunities"
          value={summary.data?.active_opportunities ?? "—"}
        />
        <Stat
          label="Needing follow-up"
          value={summary.data?.accounts_needing_follow_up ?? "—"}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Panel title="Accounts">
          {accounts.isLoading ? (
            <Empty>Loading…</Empty>
          ) : !accounts.data || accounts.data.length === 0 ? (
            <Empty>No accounts yet.</Empty>
          ) : (
            <ul className="divide-y divide-border">
              {accounts.data.map((a) => (
                <li key={a.id} className="flex items-center justify-between py-2">
                  <div className="min-w-0">
                    <div className="truncate font-medium">{a.name}</div>
                    <div className="text-xs text-muted">
                      {[a.sector, a.region, a.type].filter(Boolean).join(" · ") || "—"}
                    </div>
                  </div>
                  {a.type && <Pill tone="default">{a.type}</Pill>}
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Campaigns">
          {campaigns.isLoading ? (
            <Empty>Loading…</Empty>
          ) : !campaigns.data || campaigns.data.length === 0 ? (
            <Empty>No campaigns yet.</Empty>
          ) : (
            <ul className="divide-y divide-border">
              {campaigns.data.map((c) => (
                <li key={c.id} className="flex items-center justify-between py-2">
                  <div className="min-w-0">
                    <div className="truncate font-medium">{c.name}</div>
                    <div className="text-xs text-muted">
                      {[c.sector, c.region].filter(Boolean).join(" · ") || "—"}
                    </div>
                  </div>
                  <Pill tone={c.status === "active" ? "ok" : "default"}>
                    {c.status}
                  </Pill>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Market opportunities">
          {opps.isLoading ? (
            <Empty>Loading…</Empty>
          ) : !opps.data || opps.data.length === 0 ? (
            <Empty>No opportunities yet.</Empty>
          ) : (
            <ul className="divide-y divide-border">
              {opps.data.map((o) => (
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
                  <Pill
                    tone={
                      o.stage === "active"
                        ? "ok"
                        : o.stage === "exploring"
                          ? "accent"
                          : o.stage === "closed"
                            ? "default"
                            : "warn"
                    }
                  >
                    {o.stage}
                  </Pill>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Follow-ups due">
          {followUps.isLoading ? (
            <Empty>Loading…</Empty>
          ) : !followUps.data || followUps.data.length === 0 ? (
            <Empty>No follow-ups due.</Empty>
          ) : (
            <ul className="divide-y divide-border">
              {followUps.data.map((l) => (
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
  );
}
