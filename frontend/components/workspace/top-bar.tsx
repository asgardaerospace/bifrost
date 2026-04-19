"use client";

import { useWorkspace } from "./workspace-context";

export function TopBar() {
  const { setPaletteOpen, running, toast } = useWorkspace();
  return (
    <header className="flex h-10 shrink-0 items-center justify-between border-b border-border bg-panel px-3">
      <div className="flex items-center gap-4">
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-2xs uppercase tracking-[0.25em] text-muted">
            asgard
          </span>
          <span className="font-semibold text-inkhi">Bifrost</span>
          <span className="chip">command</span>
        </div>
      </div>

      <button
        onClick={() => setPaletteOpen(true)}
        className="group flex w-[520px] max-w-[50vw] items-center gap-2 border border-border bg-bg px-3 py-1 text-left text-sm text-muted hover:border-border2 hover:text-ink"
      >
        <span className="font-mono text-2xs uppercase tracking-wider text-muted group-hover:text-ink">
          cmd
        </span>
        <span className="flex-1 truncate">
          type a command — brief me, rank pipeline, draft follow-up…
        </span>
        <span className="kbd">⌘K</span>
      </button>

      <div className="flex items-center gap-3 text-2xs font-mono uppercase tracking-wider">
        {running && <span className="text-blue">● running</span>}
        {toast && (
          <span
            className={
              toast.tone === "ok"
                ? "text-green"
                : toast.tone === "err"
                ? "text-red"
                : "text-blue"
            }
          >
            {toast.msg.slice(0, 80)}
          </span>
        )}
        <span className="text-muted">ui · phase 1</span>
      </div>
    </header>
  );
}
