import type { ClarificationOutput } from "@/types/api";
import { Panel, Pill } from "@/components/ui";

export function ClarificationOutputView({
  output,
}: {
  output: ClarificationOutput;
}) {
  return (
    <Panel
      title="Clarification needed"
      right={<Pill tone="warn">ambiguous</Pill>}
    >
      <div className="text-base font-medium">{output.headline}</div>
      <p className="mt-2 text-sm text-ink/90">{output.message}</p>
      {output.candidates.length > 0 && (
        <div className="mt-3">
          <div className="font-mono text-[10px] uppercase tracking-widest text-muted">
            Candidates
          </div>
          <ul className="mt-2 space-y-1 text-sm">
            {output.candidates.map((c, i) => (
              <li key={i}>
                {c.label ?? `${c.entity_type} #${c.entity_id}`}
              </li>
            ))}
          </ul>
        </div>
      )}
      {output.suggested_inputs.length > 0 && (
        <div className="mt-3">
          <div className="font-mono text-[10px] uppercase tracking-widest text-muted">
            Try
          </div>
          <ul className="mt-1 space-y-1 font-mono text-sm text-accent">
            {output.suggested_inputs.map((s, i) => (
              <li key={i}>› {s}</li>
            ))}
          </ul>
        </div>
      )}
    </Panel>
  );
}
