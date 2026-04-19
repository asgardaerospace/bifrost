"use client";

import { WorkspaceProvider } from "./workspace-context";
import { TopBar } from "./top-bar";
import { Briefing } from "./briefing";
import { ActionQueue } from "./action-queue";
import { ContextPanel } from "./context-panel";
import { CommandBar } from "./command-bar";

export function Workspace() {
  return (
    <WorkspaceProvider>
      <div className="flex h-screen flex-col bg-bg text-ink">
        <TopBar />
        <div className="grid min-h-0 flex-1 grid-cols-[300px_1fr_360px]">
          <Briefing />
          <ActionQueue />
          <ContextPanel />
        </div>
        <CommandBar />
      </div>
    </WorkspaceProvider>
  );
}
