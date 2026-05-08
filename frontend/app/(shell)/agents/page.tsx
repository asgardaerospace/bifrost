"use client";

import { useState } from "react";

import { AgentActivityRail } from "@/components/shell/agent-activity-rail";
import { PendingActionsPanel } from "@/components/shell/pending-actions-panel";
import { WorkflowTraceViewer } from "@/components/shell/workflow-trace-viewer";

export default function AgentsPage() {
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);

  return (
    <div className="flex flex-col gap-4 p-6">
      <header className="flex items-end justify-between">
        <div>
          <div className="font-mono text-2xs uppercase tracking-[0.3em] text-accent/80">
            ▸ governed agent coordination
          </div>
          <h1 className="mt-2 text-2xl font-semibold text-inkhi text-accent-glow">
            Agents
          </h1>
          <p className="mt-1 max-w-3xl text-sm text-mute2">
            Finite, registered, retrieval-grounded agents. Every run is
            auditable. Every proposed action is approval-gated. Humans remain
            in command — agents never mutate operational state directly.
          </p>
        </div>
      </header>

      <PendingActionsPanel />

      <AgentActivityRail
        selectedRunId={selectedRunId}
        onSelectRun={setSelectedRunId}
      />

      <WorkflowTraceViewer operationId={selectedRunId} />
    </div>
  );
}
