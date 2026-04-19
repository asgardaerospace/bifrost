import Link from "next/link";
import type { EngineListOutput } from "@/types/api";
import { Pill, SourceBadge, formatDate, relative } from "@/components/ui";

export function EngineListOutputView({
  output,
}: {
  output: EngineListOutput;
}) {
  const stageCounts = Object.entries(output.counts)
    .filter(([k]) => k.startsWith("stage."))
    .map(([k, v]) => [k.replace("stage.", ""), v] as const);
  const followUpCounts = Object.entries(output.counts)
    .filter(([k]) => k.startsWith("follow_up."))
    .map(([k, v]) => [k.replace("follow_up.", ""), v] as const);

  return (
    <div className="space-y-3">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold">{output.headline}</h3>
          <SourceBadge source="investor_engine" />
        </div>
      </header>

      {output.rationale && (
        <p className="text-xs text-muted">{output.rationale}</p>
      )}

      {(stageCounts.length > 0 || followUpCounts.length > 0) && (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {stageCounts.length > 0 && (
            <div className="rounded border border-border bg-bg/40 p-3">
              <div className="mb-2 font-mono text-[10px] uppercase tracking-widest text-muted">
                By stage
              </div>
              <div className="flex flex-wrap gap-2">
                {stageCounts.map(([k, v]) => (
                  <span key={k} className="text-xs">
                    <span className="text-muted">{k}</span>{" "}
                    <span className="tabular-nums">{v}</span>
                  </span>
                ))}
              </div>
            </div>
          )}
          {followUpCounts.length > 0 && (
            <div className="rounded border border-border bg-bg/40 p-3">
              <div className="mb-2 font-mono text-[10px] uppercase tracking-widest text-muted">
                By follow-up
              </div>
              <div className="flex flex-wrap gap-2">
                {followUpCounts.map(([k, v]) => (
                  <span key={k} className="text-xs">
                    <span className="text-muted">{k}</span>{" "}
                    <span className="tabular-nums">{v}</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {output.investors.length > 0 && (
        <ul className="divide-y divide-border">
          {output.investors.map((n) => (
            <li
              key={n.external_id}
              className="flex items-start justify-between gap-3 py-2"
            >
              <div className="min-w-0">
                <Link
                  href={`/engine/${encodeURIComponent(n.external_id)}`}
                  className="truncate font-medium hover:underline"
                >
                  {n.firm_name}
                </Link>
                <div className="text-xs text-muted">
                  {n.stage ?? "—"}
                  {n.owner ? ` · ${n.owner}` : ""}
                  {n.last_touch_at
                    ? ` · last touch ${relative(n.last_touch_at)}`
                    : ""}
                </div>
                {n.next_step && (
                  <div className="mt-1 truncate text-xs">{n.next_step}</div>
                )}
              </div>
              <div className="flex flex-col items-end gap-1">
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
                {n.next_follow_up_at && (
                  <span className="text-[11px] text-muted">
                    due {formatDate(n.next_follow_up_at)}
                  </span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
