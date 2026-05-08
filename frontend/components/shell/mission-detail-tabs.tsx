"use client";

import { useState, type ReactNode } from "react";

export type MissionTabKey =
  | "overview"
  | "entities"
  | "timeline"
  | "queue"
  | "dependencies";

export interface MissionTabSpec {
  key: MissionTabKey;
  label: string;
  badge?: number | string;
}

export function MissionDetailTabs({
  tabs,
  active,
  onChange,
}: {
  tabs: MissionTabSpec[];
  active: MissionTabKey;
  onChange: (key: MissionTabKey) => void;
}) {
  return (
    <nav className="flex items-center gap-1 border-b border-border/60">
      {tabs.map((t) => {
        const isActive = t.key === active;
        return (
          <button
            key={t.key}
            onClick={() => onChange(t.key)}
            className={
              "relative flex items-center gap-2 px-3 py-2 font-mono text-2xs uppercase tracking-widest transition-colors " +
              (isActive
                ? "text-accent text-accent-glow"
                : "text-mute2 hover:text-ink")
            }
            type="button"
          >
            <span>{t.label}</span>
            {t.badge !== undefined && t.badge !== null && t.badge !== "" && (
              <span className="chip text-[10px]">{t.badge}</span>
            )}
            {isActive && (
              <span className="absolute inset-x-2 bottom-0 h-px bg-gradient-to-r from-transparent via-accent to-transparent" />
            )}
          </button>
        );
      })}
    </nav>
  );
}

export function MissionTabPanel({ children }: { children: ReactNode }) {
  return <div className="py-4">{children}</div>;
}

export function useMissionTab(initial: MissionTabKey = "overview") {
  return useState<MissionTabKey>(initial);
}
