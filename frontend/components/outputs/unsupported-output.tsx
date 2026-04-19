import type { UnsupportedOutput } from "@/types/api";
import { Panel, Pill } from "@/components/ui";

export function UnsupportedOutputView({
  output,
}: {
  output: UnsupportedOutput;
}) {
  return (
    <Panel
      title="Unsupported command"
      right={<Pill tone="danger">out of scope</Pill>}
    >
      <div className="text-base font-medium">{output.headline}</div>
      <p className="mt-2 text-sm text-muted">{output.reason}</p>
      {output.supported_examples.length > 0 && (
        <div className="mt-4">
          <div className="font-mono text-[10px] uppercase tracking-widest text-muted">
            Supported examples
          </div>
          <ul className="mt-2 space-y-1 font-mono text-sm text-accent">
            {output.supported_examples.map((s, i) => (
              <li key={i}>› {s}</li>
            ))}
          </ul>
        </div>
      )}
    </Panel>
  );
}
