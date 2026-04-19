"use client";

import { useEffect, useState } from "react";
import { useWorkspace } from "./workspace-context";

export function TopBar() {
  const { setPaletteOpen, running, toast } = useWorkspace();
  const [time, setTime] = useState<string>("");

  useEffect(() => {
    const tick = () => {
      const d = new Date();
      setTime(
        d.toISOString().slice(11, 19) + " Z",
      );
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <header className="relative flex h-11 shrink-0 items-center justify-between border-b border-border/80 bg-panel/70 px-3 glass-strong hairline-accent">
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-accent/40 to-transparent" />

      <div className="flex items-center gap-4">
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-2xs uppercase tracking-[0.3em] text-accent/70">
            asgard
          </span>
          <span className="relative font-semibold text-inkhi text-accent-glow">
            Bifrost
          </span>
          <span className="chip-accent">command</span>
        </div>
        <div className="hidden items-center gap-2 border-l border-border2 pl-4 text-2xs font-mono uppercase tracking-wider md:flex">
          <span className="flex items-center gap-1.5 text-mute2">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-soft-pulse rounded-full bg-green/80" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-green" />
            </span>
            link
          </span>
          <span className="text-muted">·</span>
          <span className="text-mute2">engine</span>
          <span className="text-muted">·</span>
          <span className="text-mute2">observers</span>
        </div>
      </div>

      <button
        onClick={() => setPaletteOpen(true)}
        className="group flex w-[560px] max-w-[50vw] items-center gap-2 border border-border2 bg-panel2/70 px-3 py-1.5 text-left text-sm text-muted shadow-[inset_0_0_0_1px_rgba(34,211,238,0.04)] transition-all hover:border-accent/50 hover:bg-panel2 hover:text-ink hover:shadow-glow-sm"
      >
        <span className="font-mono text-2xs uppercase tracking-wider text-accent/60 group-hover:text-accent">
          ▸ cmd
        </span>
        <span className="flex-1 truncate">
          type a command — brief me, rank pipeline, draft follow-up…
        </span>
        <span className="kbd">⌘K</span>
      </button>

      <div className="flex items-center gap-3 text-2xs font-mono uppercase tracking-wider">
        {running && (
          <span className="flex items-center gap-1 text-accent animate-fade-in">
            <span className="inline-block h-1.5 w-1.5 animate-soft-pulse rounded-full bg-accent" />
            running
          </span>
        )}
        {toast && (
          <span
            className={`animate-fade-in ${
              toast.tone === "ok"
                ? "text-green"
                : toast.tone === "err"
                ? "text-red"
                : "text-accent"
            }`}
          >
            {toast.msg.slice(0, 80)}
          </span>
        )}
        <span className="text-muted">{time}</span>
        <span className="text-muted">· ph1</span>
      </div>
    </header>
  );
}
