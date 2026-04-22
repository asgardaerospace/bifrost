"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useEffect, useMemo, useRef, useState } from "react";
import type { ActionItem } from "@/types/api";
import { useWorkspace } from "./workspace-context";
import { StatusDot, fmtRelative } from "./format";

type SortKey = "priority" | "due" | "domain";
const DOMAINS = [
  "all",
  "capital",
  "market",
  "program",
  "supplier",
  "approval",
  "engine",
  "intel",
] as const;

export function ActionQueue() {
  const { selected, setSelected, runCommand } = useWorkspace();
  const [domain, setDomain] = useState<(typeof DOMAINS)[number]>("all");
  const [sort, setSort] = useState<SortKey>("priority");
  const [cursor, setCursor] = useState(0);
  const [collapsed, setCollapsed] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["action-queue", domain],
    queryFn: () =>
      api.executiveActionQueue({
        domain: domain === "all" ? undefined : domain,
        limit: 80,
      }),
  });

  const items = useMemo(() => {
    const base = data?.items ?? [];
    const copy = [...base];
    if (sort === "priority") {
      copy.sort((a, b) => b.priority_score - a.priority_score);
    } else if (sort === "due") {
      copy.sort((a, b) => {
        const ax = a.due_at ? new Date(a.due_at).getTime() : Infinity;
        const bx = b.due_at ? new Date(b.due_at).getTime() : Infinity;
        return ax - bx;
      });
    } else if (sort === "domain") {
      copy.sort((a, b) => a.domain.localeCompare(b.domain));
    }
    return copy;
  }, [data, sort]);

  useEffect(() => {
    if (cursor >= items.length) setCursor(Math.max(0, items.length - 1));
  }, [items.length, cursor]);

  const autoSelectedRef = useRef(false);
  useEffect(() => {
    if (autoSelectedRef.current) return;
    if (selected) {
      autoSelectedRef.current = true;
      return;
    }
    if (items.length === 0) return;
    autoSelectedRef.current = true;
    openAction(items[0], setSelected);
  }, [items, selected, setSelected]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const typing =
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable);
      if (typing) return;
      if (e.key === "j" || e.key === "ArrowDown") {
        e.preventDefault();
        setCursor((c) => Math.min(c + 1, items.length - 1));
      } else if (e.key === "k" || e.key === "ArrowUp") {
        e.preventDefault();
        setCursor((c) => Math.max(c - 1, 0));
      } else if (e.key === "Enter" || e.key === "l") {
        const it = items[cursor];
        if (it) openAction(it, setSelected);
      } else if (e.key === "d") {
        const it = items[cursor];
        if (it && it.domain === "capital" && it.related_entity_id) {
          runCommand(`draft follow-up for opportunity ${it.related_entity_id}`);
        }
      } else if (e.key === "b") {
        const it = items[cursor];
        if (it && it.related_entity_id) {
          runCommand(`brief on ${it.related_entity_type} ${it.related_entity_id}`);
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [items, cursor, setSelected, runCommand]);

  const criticalCount = items.filter((i) => i.priority_score >= 80).length;
  const warnCount = items.filter(
    (i) => i.priority_score >= 50 && i.priority_score < 80,
  ).length;

  return (
    <section
      className={`flex shrink-0 flex-col border-t border-accent/20 bg-panel/70 glass-strong transition-[height] duration-200 ${
        collapsed ? "h-10" : "h-[280px]"
      }`}
    >
      <header className="relative flex shrink-0 items-center justify-between border-b border-border/80 px-3 py-1.5">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent/40 to-transparent" />
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="inline-block h-1.5 w-1.5 animate-soft-pulse rounded-full bg-accent" />
            <h2 className="font-mono text-2xs uppercase tracking-[0.3em] text-accent">
              execution queue
            </h2>
          </div>
          <span className="text-2xs text-muted">
            {items.length} {items.length === 1 ? "item" : "items"}
          </span>
          {criticalCount > 0 && (
            <span className="chip border-red/50 bg-red/10 text-red">
              crit {criticalCount}
            </span>
          )}
          {warnCount > 0 && (
            <span className="chip border-amber/50 bg-amber/10 text-amber">
              warn {warnCount}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {DOMAINS.map((d) => (
            <button
              key={d}
              onClick={() => setDomain(d)}
              className={`px-2 py-0.5 font-mono text-2xs uppercase tracking-wider transition-colors ${
                domain === d
                  ? "border border-accent/40 bg-accent/10 text-accent"
                  : "border border-transparent text-muted hover:text-ink"
              }`}
            >
              {d}
            </button>
          ))}
          <div className="ml-2 flex items-center gap-1 border-l border-border2 pl-2">
            <span className="text-2xs text-muted">sort:</span>
            {(["priority", "due", "domain"] as SortKey[]).map((s) => (
              <button
                key={s}
                onClick={() => setSort(s)}
                className={`px-1.5 py-0.5 font-mono text-2xs uppercase tracking-wider ${
                  sort === s ? "text-accent" : "text-muted hover:text-ink"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
          <button
            onClick={() => refetch()}
            className="ml-2 border border-border2 bg-panel2 px-1.5 py-0.5 font-mono text-2xs uppercase tracking-wider text-muted hover:border-accent hover:text-accent"
            title="Refresh"
          >
            refresh
          </button>
          <button
            onClick={() => setCollapsed((c) => !c)}
            className="ml-1 border border-border2 bg-panel2 px-1.5 py-0.5 font-mono text-2xs uppercase tracking-wider text-muted hover:text-accent"
          >
            {collapsed ? "expand" : "collapse"}
          </button>
        </div>
      </header>

      {!collapsed && (
        <>
          <div ref={listRef} className="flex-1 overflow-y-auto">
            {isLoading && (
              <div className="p-4 text-sm text-muted">loading queue…</div>
            )}
            {!isLoading && error && (
              <div className="p-4 text-sm">
                <div className="font-mono text-2xs uppercase tracking-widest text-red">
                  action queue failed to load
                </div>
                <div className="mt-1 text-xs text-muted break-words">
                  {(error as Error).message}
                </div>
                <button
                  onClick={() => refetch()}
                  className="mt-2 border border-border2 bg-panel2 px-2 py-1 font-mono text-2xs uppercase tracking-wider text-ink hover:border-accent hover:text-accent"
                >
                  retry
                </button>
              </div>
            )}
            {!isLoading && !error && items.length === 0 && (
              <div className="p-4 text-sm text-muted">
                queue clear · no actions
              </div>
            )}
            {items.map((it, i) => (
              <ActionRow
                key={it.id}
                item={it}
                index={i}
                active={i === cursor}
                selected={selected?.id === it.id}
                onFocus={() => setCursor(i)}
                onOpen={() => openAction(it, setSelected)}
                onDraft={() =>
                  it.related_entity_id &&
                  runCommand(
                    `draft follow-up for opportunity ${it.related_entity_id}`,
                  )
                }
                onBrief={() =>
                  it.related_entity_id &&
                  runCommand(
                    `brief on ${it.related_entity_type} ${it.related_entity_id}`,
                  )
                }
              />
            ))}
          </div>

          <footer className="flex shrink-0 items-center justify-between border-t border-border/80 bg-panel/60 px-3 py-1 font-mono text-2xs uppercase tracking-wider text-muted">
            <div className="flex items-center gap-3">
              <span>
                <span className="kbd">j/k</span> move
              </span>
              <span>
                <span className="kbd">enter</span> open
              </span>
              <span>
                <span className="kbd">d</span> draft
              </span>
              <span>
                <span className="kbd">b</span> brief
              </span>
              <span>
                <span className="kbd">⌘K</span> cmd
              </span>
            </div>
            {data?.generated_at && (
              <span>generated {fmtRelative(data.generated_at)}</span>
            )}
          </footer>
        </>
      )}
    </section>
  );
}

function openAction(
  it: ActionItem,
  setSelected: ReturnType<typeof useWorkspace>["setSelected"],
) {
  setSelected({
    kind: "action",
    id: it.id,
    ref:
      it.related_entity_type && it.related_entity_id
        ? `${it.related_entity_type}#${it.related_entity_id}`
        : undefined,
    label: it.title,
    action: it,
    entityType: it.related_entity_type ?? undefined,
    entityId: it.related_entity_id ?? undefined,
  });
}

function priorityTone(p: number): "red" | "amber" | "blue" | "green" {
  if (p >= 80) return "red";
  if (p >= 50) return "amber";
  if (p >= 20) return "blue";
  return "green";
}

function ActionRow({
  item,
  index,
  active,
  selected,
  onFocus,
  onOpen,
  onDraft,
  onBrief,
}: {
  item: ActionItem;
  index: number;
  active: boolean;
  selected: boolean;
  onFocus: () => void;
  onOpen: () => void;
  onDraft: () => void;
  onBrief: () => void;
}) {
  const tone = priorityTone(item.priority_score);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (active) ref.current?.scrollIntoView({ block: "nearest" });
  }, [active]);

  const toneBar =
    tone === "red"
      ? "bg-red"
      : tone === "amber"
      ? "bg-amber"
      : tone === "green"
      ? "bg-green"
      : "bg-accent";

  const activeGlow = selected
    ? "shadow-[inset_3px_0_0_0_rgba(34,211,238,1),0_0_16px_-4px_rgba(34,211,238,0.4)]"
    : active
    ? "shadow-[inset_3px_0_0_0_rgba(34,211,238,0.5)]"
    : "";

  return (
    <div
      ref={ref}
      onMouseEnter={onFocus}
      onClick={onOpen}
      className={`group relative grid cursor-pointer grid-cols-[4px_28px_72px_80px_1fr_90px_auto] items-center gap-2 border-b border-border/60 px-3 py-1.5 text-sm transition-colors ${
        selected
          ? "bg-accent/10 text-inkhi"
          : active
          ? "bg-panel2 text-ink"
          : "text-mute2 hover:bg-panel2/60"
      } ${activeGlow}`}
    >
      <span className={`h-full w-0.5 ${toneBar} opacity-${selected ? 100 : active ? 70 : 40}`} />
      <span className="font-mono text-2xs text-muted">
        {String(index + 1).padStart(2, "0")}
      </span>
      <span className="flex items-center gap-1.5">
        <StatusDot tone={tone} />
        <span className="font-mono tabular-nums text-2xs text-mute2">
          {Math.round(item.priority_score)}
        </span>
      </span>
      <span className="truncate font-mono text-2xs uppercase tracking-wider text-muted">
        {item.domain}
      </span>
      <span className="truncate">
        <span className="text-ink">{item.title}</span>
        {item.description && (
          <span className="ml-2 text-muted">· {item.description}</span>
        )}
      </span>
      <span className="text-right font-mono text-2xs text-mute2">
        {fmtRelative(item.due_at)}
      </span>
      <span className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
        {item.domain === "capital" && item.related_entity_id && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDraft();
            }}
            className="border border-border2 bg-panel2 px-1.5 py-0.5 font-mono text-2xs uppercase tracking-wider hover:border-accent hover:text-accent"
            title="Draft follow-up (d)"
          >
            draft
          </button>
        )}
        {item.related_entity_id && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onBrief();
            }}
            className="border border-border2 bg-panel2 px-1.5 py-0.5 font-mono text-2xs uppercase tracking-wider hover:border-accent hover:text-accent"
            title="Brief (b)"
          >
            brief
          </button>
        )}
      </span>
    </div>
  );
}
