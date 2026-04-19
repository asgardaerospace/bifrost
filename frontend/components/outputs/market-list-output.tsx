import type { MarketListOutput } from "@/types/api";
import { Empty, Pill, formatDate } from "@/components/ui";

export function MarketListOutputView({
  output,
}: {
  output: MarketListOutput;
}) {
  const { kind } = output;

  return (
    <div className="space-y-3">
      <header>
        <h3 className="font-semibold">{output.headline}</h3>
        {output.rationale && (
          <p className="text-xs text-muted">{output.rationale}</p>
        )}
      </header>

      {kind === "accounts" && (
        <ul className="divide-y divide-border">
          {output.accounts.length === 0 && <Empty>No accounts.</Empty>}
          {output.accounts.map((a) => (
            <li key={a.id} className="flex items-center justify-between py-2">
              <div className="min-w-0">
                <div className="truncate font-medium">{a.name}</div>
                <div className="text-xs text-muted">
                  {[a.sector, a.region].filter(Boolean).join(" · ") || "—"}
                </div>
              </div>
              {a.type && <Pill tone="default">{a.type}</Pill>}
            </li>
          ))}
        </ul>
      )}

      {kind === "campaigns" && (
        <ul className="divide-y divide-border">
          {output.campaigns.length === 0 && <Empty>No campaigns.</Empty>}
          {output.campaigns.map((c) => (
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

      {kind === "opportunities" && (
        <ul className="divide-y divide-border">
          {output.opportunities.length === 0 && <Empty>No opportunities.</Empty>}
          {output.opportunities.map((o) => (
            <li key={o.id} className="flex items-start justify-between py-2">
              <div className="min-w-0">
                <div className="truncate font-medium">{o.name}</div>
                <div className="text-xs text-muted">
                  {o.account_name ?? `account #${o.account_id}`}
                  {o.sector ? ` · ${o.sector}` : ""}
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

      {kind === "follow_ups" && (
        <ul className="divide-y divide-border">
          {output.follow_ups.length === 0 && <Empty>No follow-ups due.</Empty>}
          {output.follow_ups.map((l) => (
            <li key={l.link_id} className="flex items-start justify-between py-2">
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

      {kind === "by_sector" && (
        <div className="space-y-3">
          {Object.entries(output.by_sector).map(([sector, opps]) => (
            <div key={sector} className="rounded border border-border bg-bg/40">
              <div className="border-b border-border px-3 py-2 font-mono text-[11px] uppercase tracking-widest text-muted">
                {sector} · {opps.length}
              </div>
              <ul className="divide-y divide-border px-3">
                {opps.map((o) => (
                  <li
                    key={o.id}
                    className="flex items-center justify-between py-2"
                  >
                    <span className="truncate">{o.name}</span>
                    <Pill tone="accent">{o.stage}</Pill>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
