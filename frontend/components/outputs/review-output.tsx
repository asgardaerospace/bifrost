import type { ReviewOutput } from "@/types/api";
import { Empty, Panel, Pill } from "@/components/ui";

export function ReviewOutputView({ output }: { output: ReviewOutput }) {
  return (
    <div className="space-y-4">
      <Panel title="Review">
        <div className="text-base font-medium">{output.headline}</div>
      </Panel>

      <Panel title="Pending approvals">
        {output.pending_approvals.length === 0 ? (
          <Empty>No pending approvals.</Empty>
        ) : (
          <ul className="divide-y divide-border">
            {output.pending_approvals.map((it) => (
              <li
                key={`${it.entity_type}-${it.entity_id}`}
                className="flex items-center justify-between py-2"
              >
                <div className="min-w-0">
                  <div className="truncate">{it.summary}</div>
                  <div className="text-xs text-muted">
                    {it.entity_type} · {it.entity_id}
                  </div>
                </div>
                <Pill tone="warn">{it.status}</Pill>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      {output.blocked_items.length > 0 && (
        <Panel title="Blocked / incomplete">
          <ul className="divide-y divide-border">
            {output.blocked_items.map((it, i) => (
              <li key={i} className="flex items-center justify-between py-2">
                <div className="min-w-0">
                  <div className="truncate">{it.summary}</div>
                  <div className="text-xs text-muted">
                    {it.entity_type} · {it.entity_id}
                  </div>
                </div>
                <Pill tone="danger">{it.status}</Pill>
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </div>
  );
}
