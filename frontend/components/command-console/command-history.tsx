"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Empty, Panel, Pill, relative } from "@/components/ui";

export function CommandHistory() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["command-history"],
    queryFn: () => api.commandHistory(25),
  });

  return (
    <Panel
      title="Recent commands"
      right={
        <button
          onClick={() => refetch()}
          className="font-mono text-[10px] uppercase tracking-widest text-muted hover:text-accent"
        >
          refresh
        </button>
      }
    >
      {isLoading ? (
        <Empty>Loading…</Empty>
      ) : isError ? (
        <Empty>Failed to load history.</Empty>
      ) : !data || data.length === 0 ? (
        <Empty>No commands yet.</Empty>
      ) : (
        <ul className="divide-y divide-border">
          {data.map((h) => (
            <li key={h.id} className="py-2">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate font-mono text-sm">
                    {h.command_text}
                  </div>
                  <div className="mt-1 flex flex-wrap gap-2 text-[11px] text-muted">
                    <span>{relative(h.created_at)}</span>
                    {h.command_class && <span>· {h.command_class}</span>}
                    {h.output_type && <span>· {h.output_type}</span>}
                  </div>
                </div>
                <Pill
                  tone={
                    h.status === "completed"
                      ? "ok"
                      : h.status === "unsupported"
                        ? "danger"
                        : h.status === "clarification_needed"
                          ? "warn"
                          : "default"
                  }
                >
                  {h.status ?? "—"}
                </Pill>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
