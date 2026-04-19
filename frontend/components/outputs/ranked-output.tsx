import type { OpportunitySummary, RankedOutput } from "@/types/api";
import { Empty, Panel, Pill, formatDate, relative } from "@/components/ui";

export function RankedOutputView({ output }: { output: RankedOutput }) {
  const hasScored = output.items.length > 0;

  return (
    <Panel
      title="Ranked"
      right={
        <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
          {output.scoring_logic}
        </span>
      }
    >
      <div className="mb-3 text-base font-medium">{output.headline}</div>

      {hasScored ? (
        <ol className="divide-y divide-border">
          {output.items.map((it, idx) => (
            <li key={it.opportunity.id} className="py-3">
              <div className="flex items-start justify-between gap-4">
                <div className="flex min-w-0 items-baseline gap-3">
                  <span className="font-mono text-xs text-muted">
                    {String(idx + 1).padStart(2, "0")}
                  </span>
                  <div className="min-w-0">
                    <div className="truncate font-medium">
                      {it.opportunity.firm_name ??
                        `opportunity #${it.opportunity.id}`}
                    </div>
                    <div className="mt-0.5 text-sm text-muted">
                      {it.rationale}
                    </div>
                    <div className="mt-1 text-sm">
                      → {it.recommended_next_action}
                    </div>
                  </div>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-1">
                  <div className="font-mono text-lg tabular-nums">
                    {it.priority_score.toFixed(1)}
                  </div>
                  <Pill tone="accent">{it.opportunity.stage}</Pill>
                </div>
              </div>
            </li>
          ))}
        </ol>
      ) : output.opportunities.length > 0 ? (
        <OpportunityList list={output.opportunities} />
      ) : (
        <Empty>No opportunities matched.</Empty>
      )}
    </Panel>
  );
}

export function OpportunityList({ list }: { list: OpportunitySummary[] }) {
  return (
    <ul className="divide-y divide-border">
      {list.map((o) => (
        <li key={o.id} className="flex items-start justify-between gap-4 py-3">
          <div className="min-w-0">
            <div className="truncate font-medium">
              {o.firm_name ?? `opportunity #${o.id}`}
            </div>
            <div className="mt-0.5 text-sm text-muted">
              {o.next_step ?? "No next step defined"}
            </div>
            <div className="mt-1 flex flex-wrap gap-3 text-xs text-muted">
              <span>stage: {o.stage}</span>
              {o.next_step_due_at && (
                <span>due: {formatDate(o.next_step_due_at)}</span>
              )}
              {o.last_interaction_at && (
                <span>last: {relative(o.last_interaction_at)}</span>
              )}
              {o.owner && <span>owner: {o.owner}</span>}
            </div>
          </div>
          <Pill tone="accent">{o.stage}</Pill>
        </li>
      ))}
    </ul>
  );
}
