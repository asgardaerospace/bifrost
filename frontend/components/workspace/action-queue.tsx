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
] as const;

export function ActionQueue() {
  const { selected, setSelected, runCommand } = useWorkspace();
  const [domain, setDomain] = useState<(typeof DOMAINS)[number]>("all");
  const [sort, setSort] = useState<SortKey>("priority");
  const [cursor, setCursor] = useState(0);
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

  return (
    <section className="flex h-full min-h-0 flex-col border-r border-border bg-bg">
      <header className="flex items-center justify-between border-b border-border bg-panel px-3 py-2">
        <div className="flex items-center gap-3">
          <h2 className="font-mono text-2xs uppercase tracking-widest text-mute2">
            action queue
          </h2>
          <span className="text-2xs text-muted">
            {items.length} {items.length === 1 ? "item" : "items"}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {DOMAINS.map((d) => (
            <button
              key={d}
              onClick={() => setDomain(d)}
              className={`px-2 py-0.5 font-mono text-2xs uppercase tracking-wider ${
                domain === d
                  ? "border border-border2 bg-panel2 text-inkhi"
                  : "text-muted hover:text-ink"
              }`}
            >
              {d}
            </button>
          ))}
          <div className="ml-2 flex items-center gap-1 border-l border-border pl-2">
            <span className="text-2xs text-muted">sort:</span>
            {(["priority", "due", "domain"] as SortKey[]).map((s) => (
              <button
                key={s}
                onClick={() => setSort(s)}
                className={`px-1.5 py-0.5 font-mono text-2xs uppercase tracking-wider ${
                  sort === s ? "text-inkhi" : "text-muted hover:text-ink"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
          <button
            onClick={() => refetch()}
            className="ml-2 border border-border bg-panel2 px-1.5 py-0.5 font-mono text-2xs uppercase tracking-wider text-muted hover:text-ink"
            title="Refresh"
          >
            refresh
          </button>
        </div>
      </header>

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
              className="mt-2 border border-border2 bg-panel2 px-2 py-1 font-mono text-2xs uppercase tracking-wider text-ink hover:border-blue hover:text-blue"
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

      <footer className="flex items-center justify-between border-t border-border bg-panel px-3 py-1 font-mono text-2xs uppercase tracking-wider text-muted">
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
  return (
    <div
      ref={ref}
      onMouseEnter={onFocus}
      onClick={onOpen}
      className={`group grid cursor-pointer grid-cols-[24px_60px_80px_1fr_90px_auto] items-center gap-2 border-b border-border px-3 py-1.5 text-sm ${
        selected
          ? "bg-panel2 text-inkhi"
          : active
          ? "bg-panel text-ink"
          : "text-mute2 hover:bg-panel"
      }`}
    >
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
            className="border border-border bg-panel2 px-1.5 py-0.5 font-mono text-2xs uppercase tracking-wider hover:border-blue hover:text-blue"
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
            className="border border-border bg-panel2 px-1.5 py-0.5 font-mono text-2xs uppercase tracking-wider hover:border-blue hover:text-blue"
            title="Brief (b)"
          >
            brief
          </button>
        )}
      </span>
    </div>
  );
}
