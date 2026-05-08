"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { ExecutionQueueItemRead } from "@/types/api";

import { useShell } from "./shell-context";

const TYPE_TONE: Record<string, string> = {
  task: "text-cyan",
  approval: "text-amber",
  draft: "text-teal",
  followup: "text-blue",
  recommendation: "text-accent",
  mission_action: "text-inkhi",
  blocker: "text-red",
};

function priorityBadge(score: number) {
  if (score >= 75) return { label: "critical", tone: "text-red" };
  if (score >= 55) return { label: "high", tone: "text-amber" };
  if (score >= 30) return { label: "normal", tone: "text-mute2" };
  return { label: "low", tone: "text-mute2" };
}

function QueueItemRow({
  item,
  onClick,
  isFocused,
}: {
  item: ExecutionQueueItemRead;
  onClick: () => void;
  isFocused: boolean;
}) {
  const tone = TYPE_TONE[item.item_type] ?? "text-mute2";
  const pri = priorityBadge(item.priority_score);
  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        className={
          "w-full rounded-md border bg-panel2/50 p-2 text-left transition-colors " +
          (isFocused
            ? "border-accent shadow-glow-sm bg-panel3/70"
            : "border-border/60 hover:border-accent/40 hover:bg-panel3/60")
        }
      >
        <div className="flex items-center justify-between font-mono text-[10px] uppercase tracking-wider">
          <span className={tone}>{item.item_type}</span>
          <span className={pri.tone}>{pri.label}</span>
        </div>
        <div className="mt-1 line-clamp-2 text-xs text-ink">{item.title}</div>
        <div className="mt-1 flex items-center gap-2 font-mono text-[10px] text-mute2">
          {item.owner && <span>@{item.owner}</span>}
          {item.due_at && (
            <span>due {new Date(item.due_at).toLocaleDateString()}</span>
          )}
          {item.requires_approval && (
            <span className="chip text-amber">approval-gated</span>
          )}
          {item.is_projected && <span className="ml-auto chip">projected</span>}
          {item.source_type && !item.is_projected && (
            <span className="ml-auto font-mono text-[10px] text-mute2">
              {item.source_type}
            </span>
          )}
        </div>
      </button>
    </li>
  );
}

export function TacticalRail() {
  const {
    selectedMissionId,
    focusedQueueItemId,
    setFocusedQueueItemId,
  } = useShell();
  const missionId = selectedMissionId ?? undefined;

  const { data: queue, isLoading } = useQuery({
    queryKey: ["execution", "queue", missionId ?? "all"],
    queryFn: () => api.executionQueue({ mission_id: missionId, limit: 30 }),
    staleTime: 15_000,
  });
  const { data: blockers } = useQuery({
    queryKey: ["execution", "blockers", missionId ?? "all"],
    queryFn: () => api.executionBlockers(missionId),
    staleTime: 15_000,
  });
  const { data: approvals } = useQuery({
    queryKey: ["execution", "approvals", missionId ?? "all"],
    queryFn: () => api.executionPendingApprovals(missionId),
    staleTime: 15_000,
  });

  function focusItem(item: ExecutionQueueItemRead) {
    setFocusedQueueItemId(item.id ?? null);
  }
  function isFocused(item: ExecutionQueueItemRead) {
    return item.id !== null && item.id === focusedQueueItemId;
  }

  return (
    <aside className="relative flex h-full min-h-0 flex-col border-l border-accent/20 bg-panel/60 glass-strong">
      <div className="pointer-events-none absolute inset-y-0 left-0 w-px bg-gradient-to-b from-transparent via-accent/40 to-transparent" />

      <div className="flex items-center justify-between border-b border-border/80 px-3 py-2">
        <span className="font-mono text-2xs uppercase tracking-[0.3em] text-accent/80">
          ▸ tactical
        </span>
        <span className="font-mono text-2xs text-mute2">
          {missionId ? `mission #${missionId}` : "all missions"}
          {" · "}
          q{queue?.count ?? 0} · b{blockers?.count ?? 0} · a{approvals?.count ?? 0}
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-3">
        <section>
          <header className="px-1 py-1 font-mono text-[10px] uppercase tracking-wider text-amber">
            ⚠ blockers · {blockers?.count ?? 0}
          </header>
          <ul className="flex flex-col gap-1.5">
            {(blockers?.items ?? []).slice(0, 5).map((it, i) => (
              <QueueItemRow
                key={`b${i}`}
                item={it}
                onClick={() => focusItem(it)}
                isFocused={isFocused(it)}
              />
            ))}
            {!isLoading && (blockers?.count ?? 0) === 0 && (
              <li className="px-1 py-1 font-mono text-[10px] text-mute2">
                no blockers
              </li>
            )}
          </ul>
        </section>

        <section>
          <header className="px-1 py-1 font-mono text-[10px] uppercase tracking-wider text-accent">
            ✓ approvals · {approvals?.count ?? 0}
          </header>
          <ul className="flex flex-col gap-1.5">
            {(approvals?.items ?? []).slice(0, 5).map((it, i) => (
              <QueueItemRow
                key={`a${i}`}
                item={it}
                onClick={() => focusItem(it)}
                isFocused={isFocused(it)}
              />
            ))}
            {!isLoading && (approvals?.count ?? 0) === 0 && (
              <li className="px-1 py-1 font-mono text-[10px] text-mute2">
                no approvals queued
              </li>
            )}
          </ul>
        </section>

        <section>
          <header className="px-1 py-1 font-mono text-[10px] uppercase tracking-wider text-mute2">
            ▸ queue · {queue?.count ?? 0}
          </header>
          <ul className="flex flex-col gap-1.5">
            {(queue?.items ?? []).slice(0, 12).map((it, i) => (
              <QueueItemRow
                key={`q${i}`}
                item={it}
                onClick={() => focusItem(it)}
                isFocused={isFocused(it)}
              />
            ))}
            {!isLoading && (queue?.count ?? 0) === 0 && (
              <li className="px-1 py-1 font-mono text-[10px] text-mute2">
                queue clear
              </li>
            )}
          </ul>
        </section>
      </div>
    </aside>
  );
}
