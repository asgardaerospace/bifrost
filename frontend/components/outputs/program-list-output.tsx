import type { ProgramListOutput, ProgramRow } from "@/types/api";
import { Empty, Pill, formatDate } from "@/components/ui";

function money(v?: number | null): string {
  if (v === null || v === undefined) return "—";
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}K`;
  return `$${v.toFixed(0)}`;
}

function stageTone(
  stage: string,
): "default" | "warn" | "danger" | "ok" | "accent" {
  switch (stage) {
    case "won":
      return "ok";
    case "lost":
      return "default";
    case "active":
      return "accent";
    case "pursuing":
      return "warn";
    default:
      return "default";
  }
}

function ProgramList({ rows }: { rows: ProgramRow[] }) {
  if (rows.length === 0) return <Empty>No programs.</Empty>;
  return (
    <ul className="divide-y divide-border">
      {rows.map((p) => (
        <li key={p.id} className="flex items-start justify-between gap-3 py-2">
          <div className="min-w-0">
            <div className="truncate font-medium">{p.name}</div>
            <div className="text-xs text-muted">
              {p.account_name ?? `account #${p.account_id}`}
              {p.owner ? ` · ${p.owner}` : ""}
              {p.next_step_due_at
                ? ` · due ${formatDate(p.next_step_due_at)}`
                : ""}
            </div>
            {p.next_step && (
              <div className="mt-1 truncate text-xs">{p.next_step}</div>
            )}
          </div>
          <div className="flex flex-col items-end gap-1">
            <Pill tone={stageTone(p.stage)}>{p.stage}</Pill>
            <span className="text-[11px] text-muted tabular-nums">
              {money(p.estimated_value)}
              {p.probability_score != null ? ` · p${p.probability_score}` : ""}
            </span>
          </div>
        </li>
      ))}
    </ul>
  );
}

export function ProgramListOutputView({
  output,
}: {
  output: ProgramListOutput;
}) {
  return (
    <div className="space-y-3">
      <header>
        <h3 className="font-semibold">{output.headline}</h3>
        {output.rationale && (
          <p className="text-xs text-muted">{output.rationale}</p>
        )}
      </header>

      {output.stage_counts.length > 0 && (
        <div className="grid grid-cols-3 gap-2 md:grid-cols-5">
          {output.stage_counts.map((s) => (
            <div
              key={s.stage}
              className="rounded border border-border bg-bg/40 px-3 py-2"
            >
              <div className="font-mono text-[10px] uppercase tracking-widest text-muted">
                {s.stage}
              </div>
              <div className="text-lg tabular-nums">{s.count}</div>
            </div>
          ))}
        </div>
      )}

      {output.totals["estimated_value_active"] !== undefined && (
        <p className="text-[11px] text-muted">
          Active pipeline value · {money(output.totals["estimated_value_active"])}
        </p>
      )}

      <ProgramList rows={output.programs} />
    </div>
  );
}
