import type { WorkflowOutput } from "@/types/api";
import { Panel, Pill, formatDate } from "@/components/ui";

export function WorkflowOutputView({ output }: { output: WorkflowOutput }) {
  const run = output.workflow_run;
  return (
    <Panel
      title="Workflow"
      right={
        output.approval_required ? (
          <Pill tone="warn">approval required</Pill>
        ) : (
          <Pill tone="ok">no approval</Pill>
        )
      }
    >
      <div className="text-base font-medium">{output.headline}</div>
      <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-muted">
            Workflow
          </div>
          <div>{output.workflow_key}</div>
        </div>
        <div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-muted">
            Run status
          </div>
          <div>{run.status}</div>
        </div>
        <div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-muted">
            Started
          </div>
          <div>{formatDate(run.started_at)}</div>
        </div>
        <div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-muted">
            Completed
          </div>
          <div>{formatDate(run.completed_at)}</div>
        </div>
      </div>
      {output.actions_created.length > 0 && (
        <div className="mt-4">
          <div className="font-mono text-[10px] uppercase tracking-widest text-muted">
            Actions created
          </div>
          <ul className="mt-2 space-y-1 text-sm">
            {output.actions_created.map((a, i) => (
              <li key={i}>→ {a}</li>
            ))}
          </ul>
        </div>
      )}
    </Panel>
  );
}
