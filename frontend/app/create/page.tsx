"use client";

import { useState } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api, type FirmCreate, type OpportunityCreate } from "@/lib/api";
import { Panel } from "@/components/ui";

const STAGES = [
  "identified",
  "qualified",
  "contacted",
  "intro_call",
  "diligence",
  "partner_meeting",
  "term_sheet",
  "decision",
  "deferred",
];

export default function CreatePage() {
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-xl font-semibold">Create</h1>
        <p className="mt-1 text-sm text-muted">
          Minimal capture forms. New records invalidate dashboard and
          command-console queries on success.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <FirmForm />
        <OpportunityForm />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// firm form
// ---------------------------------------------------------------------------

function FirmForm() {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [type_, setType] = useState("");
  const [notes, setNotes] = useState("");

  const mutation = useMutation({
    mutationFn: (payload: FirmCreate) => api.createFirm(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["firms"] });
      qc.invalidateQueries({ queryKey: ["pipeline-summary"] });
      setName("");
      setType("");
      setNotes("");
    },
  });

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || mutation.isPending) return;
    mutation.mutate({
      name: name.trim(),
      stage_focus: type_.trim() || null,
      description: notes.trim() || null,
    });
  }

  return (
    <Panel title="New investor firm">
      <form onSubmit={submit} className="space-y-3">
        <Field label="Name *">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            placeholder="Lockhart Ventures"
            className="w-full rounded-md border border-border bg-bg/40 px-3 py-2 text-sm outline-none focus:border-accent"
          />
        </Field>
        <Field label="Type (stage focus)">
          <input
            value={type_}
            onChange={(e) => setType(e.target.value)}
            placeholder="seed-to-series-a"
            className="w-full rounded-md border border-border bg-bg/40 px-3 py-2 text-sm outline-none focus:border-accent"
          />
        </Field>
        <Field label="Notes">
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            placeholder="Thesis alignment, partner relationships, etc."
            className="w-full resize-none rounded-md border border-border bg-bg/40 px-3 py-2 text-sm outline-none focus:border-accent"
          />
        </Field>
        <FormFooter
          pending={mutation.isPending}
          error={mutation.error}
          success={mutation.isSuccess ? "Firm created." : null}
          label="Create firm"
          disabled={!name.trim()}
        />
      </form>
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// opportunity form
// ---------------------------------------------------------------------------

function OpportunityForm() {
  const qc = useQueryClient();
  const firms = useQuery({
    queryKey: ["firms"],
    queryFn: () => api.listFirms(),
  });

  const [firmId, setFirmId] = useState<string>("");
  const [stage, setStage] = useState<string>("identified");
  const [nextStep, setNextStep] = useState("");
  const [dueAt, setDueAt] = useState("");

  const mutation = useMutation({
    mutationFn: (payload: OpportunityCreate) => api.createOpportunity(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pipeline-summary"] });
      qc.invalidateQueries({ queryKey: ["overdue"] });
      qc.invalidateQueries({ queryKey: ["stale"] });
      setNextStep("");
      setDueAt("");
    },
  });

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!firmId || mutation.isPending) return;
    mutation.mutate({
      firm_id: Number(firmId),
      stage,
      next_step: nextStep.trim() || null,
      next_step_due_at: dueAt ? new Date(dueAt).toISOString() : null,
    });
  }

  return (
    <Panel title="New investor opportunity">
      <form onSubmit={submit} className="space-y-3">
        <Field label="Firm *">
          <select
            value={firmId}
            onChange={(e) => setFirmId(e.target.value)}
            required
            disabled={firms.isLoading}
            className="w-full rounded-md border border-border bg-bg/40 px-3 py-2 text-sm outline-none focus:border-accent disabled:opacity-50"
          >
            <option value="" disabled>
              {firms.isLoading ? "Loading firms…" : "Select firm"}
            </option>
            {firms.data?.map((f) => (
              <option key={f.id} value={f.id}>
                {f.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Stage *">
          <select
            value={stage}
            onChange={(e) => setStage(e.target.value)}
            className="w-full rounded-md border border-border bg-bg/40 px-3 py-2 text-sm outline-none focus:border-accent"
          >
            {STAGES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Next step">
          <input
            value={nextStep}
            onChange={(e) => setNextStep(e.target.value)}
            placeholder="Send follow-up deck"
            className="w-full rounded-md border border-border bg-bg/40 px-3 py-2 text-sm outline-none focus:border-accent"
          />
        </Field>
        <Field label="Next step due">
          <input
            type="datetime-local"
            value={dueAt}
            onChange={(e) => setDueAt(e.target.value)}
            className="w-full rounded-md border border-border bg-bg/40 px-3 py-2 text-sm outline-none focus:border-accent"
          />
        </Field>
        <FormFooter
          pending={mutation.isPending}
          error={mutation.error}
          success={mutation.isSuccess ? "Opportunity created." : null}
          label="Create opportunity"
          disabled={!firmId}
        />
      </form>
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// shared helpers
// ---------------------------------------------------------------------------

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="block font-mono text-[10px] uppercase tracking-widest text-muted">
        {label}
      </span>
      <div className="mt-1">{children}</div>
    </label>
  );
}

function FormFooter({
  pending,
  error,
  success,
  label,
  disabled,
}: {
  pending: boolean;
  error: unknown;
  success: string | null;
  label: string;
  disabled: boolean;
}) {
  return (
    <div className="flex items-center gap-3 pt-1">
      <button
        type="submit"
        disabled={pending || disabled}
        className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-bg disabled:cursor-not-allowed disabled:opacity-40"
      >
        {pending ? "Saving…" : label}
      </button>
      {success && <span className="text-sm text-ok">{success}</span>}
      {error instanceof Error && (
        <span className="text-sm text-danger">{error.message}</span>
      )}
    </div>
  );
}
