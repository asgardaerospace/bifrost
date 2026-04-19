import type { SummaryOutput } from "@/types/api";
import { Panel, Pill, formatDate } from "@/components/ui";

export function SummaryOutputView({ output }: { output: SummaryOutput }) {
  const brief = output.investor_brief;
  const pipeline = output.pipeline_summary;

  return (
    <div className="space-y-4">
      <Panel title="Summary">
        <div className="text-base font-medium">{output.headline}</div>
        {output.key_insights.length > 0 && (
          <ul className="mt-3 space-y-1 text-sm text-ink/90">
            {output.key_insights.map((k, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-muted">•</span>
                <span>{k}</span>
              </li>
            ))}
          </ul>
        )}
        {output.next_actions.length > 0 && (
          <div className="mt-4">
            <div className="font-mono text-[10px] uppercase tracking-widest text-muted">
              Next actions
            </div>
            <ul className="mt-2 space-y-1 text-sm">
              {output.next_actions.map((a, i) => (
                <li key={i}>→ {a}</li>
              ))}
            </ul>
          </div>
        )}
      </Panel>

      {brief && (
        <Panel title="Investor brief">
          <div className="grid grid-cols-2 gap-3 text-sm">
            <Field label="Firm" value={brief.firm_name ?? "—"} />
            <Field label="Stage" value={brief.stage} />
            <Field
              label="Primary contact"
              value={brief.primary_contact_name ?? "—"}
            />
            <Field
              label="Last interaction"
              value={formatDate(brief.last_interaction_at)}
            />
            <Field label="Next step" value={brief.next_step ?? "—"} />
            <Field
              label="Next step due"
              value={formatDate(brief.next_step_due_at)}
            />
            <Field label="Fit" value={brief.fit_assessment} />
            <Field label="Strategic value" value={brief.strategic_value_assessment} />
          </div>
          {brief.blockers.length > 0 && (
            <div className="mt-4">
              <div className="mb-1 font-mono text-[10px] uppercase tracking-widest text-muted">
                Blockers
              </div>
              <div className="flex flex-wrap gap-2">
                {brief.blockers.map((b, i) => (
                  <Pill key={i} tone="warn">
                    {b}
                  </Pill>
                ))}
              </div>
            </div>
          )}
          {brief.missing_context.length > 0 && (
            <div className="mt-3">
              <div className="mb-1 font-mono text-[10px] uppercase tracking-widest text-muted">
                Missing context
              </div>
              <div className="flex flex-wrap gap-2">
                {brief.missing_context.map((m, i) => (
                  <Pill key={i}>{m}</Pill>
                ))}
              </div>
            </div>
          )}
          <div className="mt-4 rounded-md border border-border bg-bg/40 p-3 text-sm">
            <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
              Recommended focus
            </span>
            <div className="mt-1">{brief.recommended_executive_focus}</div>
          </div>
        </Panel>
      )}

      {pipeline && (
        <Panel title="Pipeline">
          <div className="grid grid-cols-4 gap-3">
            {pipeline.stage_counts.map((s) => (
              <div
                key={s.stage}
                className="rounded border border-border bg-bg/40 px-3 py-2"
              >
                <div className="font-mono text-[10px] uppercase tracking-widest text-muted">
                  {s.stage}
                </div>
                <div className="text-xl tabular-nums">{s.count}</div>
              </div>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div className="font-mono text-[10px] uppercase tracking-widest text-muted">
        {label}
      </div>
      <div className="mt-0.5">{value}</div>
    </div>
  );
}
