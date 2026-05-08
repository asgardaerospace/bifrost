"use client";

import type { ReactNode } from "react";

import { AwarenessBar } from "./awareness-bar";
import { ExecutionRail } from "./execution-rail";
import { IntelligenceRail } from "./intelligence-rail";
import { TacticalRail } from "./tactical-rail";

/**
 * Five-region mission-control shell per BIFROST_OPERATIONAL_UX_SYSTEM and
 * MISSION_CONTROL_INTERFACE doctrine.
 *
 * Layout:
 *   ┌──────────────────────────────────────────────────┐
 *   │              awareness bar (top)                  │
 *   ├──────────┬─────────────────────────┬─────────────┤
 *   │  intel   │      cognition          │  tactical   │
 *   │  rail    │      surface (children) │  rail       │
 *   ├──────────┴─────────────────────────┴─────────────┤
 *   │              execution rail (bottom)              │
 *   └──────────────────────────────────────────────────┘
 *
 * Sprint 0: shell-hosted routes only (`(shell)/...`). Existing CRM pages
 * (`/dashboard`, `/engine`, etc.) render outside this shell so this is
 * additive and non-breaking.
 */
export function ShellChrome({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen min-h-0 flex-col bg-bg text-ink grid-bg">
      <AwarenessBar />
      <div className="grid min-h-0 flex-1 grid-cols-[280px_1fr_340px]">
        <IntelligenceRail />
        <main className="relative min-h-0 overflow-y-auto bg-bgdeep/60">
          <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent/30 to-transparent" />
          {children}
        </main>
        <TacticalRail />
      </div>
      <ExecutionRail />
    </div>
  );
}
