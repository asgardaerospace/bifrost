"use client";

import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";

const ENTITY_TYPES = [
  { value: "investor_firm", label: "Investor firm" },
  { value: "investor_opportunity", label: "Investor opportunity" },
  { value: "account", label: "Account (Market)" },
  { value: "market_opportunity", label: "Market opportunity" },
  { value: "program", label: "Program" },
  { value: "supplier", label: "Supplier" },
  { value: "intel_item", label: "Intel signal" },
  { value: "communication", label: "Communication" },
  { value: "task", label: "Task" },
];

const RELATIONSHIP_TYPES = [
  { value: "primary", label: "Primary" },
  { value: "supporting", label: "Supporting" },
  { value: "dependency", label: "Dependency" },
  { value: "blocker", label: "Blocker" },
  { value: "beneficiary", label: "Beneficiary" },
  { value: "source", label: "Source" },
  { value: "linked", label: "Linked" },
];

export function MissionLinkDialog({
  missionId,
  open,
  onClose,
}: {
  missionId: number;
  open: boolean;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [entityType, setEntityType] = useState("investor_firm");
  const [entityId, setEntityId] = useState("");
  const [relationship, setRelationship] = useState("linked");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      api.linkMissionEntity(missionId, {
        entity_type: entityType,
        entity_id: Number(entityId),
        relationship_type: relationship,
        notes: notes.trim() || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mission", missionId, "entities"] });
      qc.invalidateQueries({ queryKey: ["mission", missionId, "entities-grouped"] });
      qc.invalidateQueries({ queryKey: ["mission", missionId, "timeline"] });
      qc.invalidateQueries({ queryKey: ["operational-events", "recent"] });
      setEntityId("");
      setNotes("");
      setError(null);
      onClose();
    },
    onError: (e: unknown) => {
      setError(e instanceof Error ? e.message : "link failed");
    },
  });

  // Reset form on open.
  useEffect(() => {
    if (open) {
      setError(null);
    }
  }, [open]);

  if (!open) return null;

  const valid = Number(entityId) > 0;

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-40 flex items-center justify-center bg-bgdeep/70 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-lg border border-accent/30 bg-panel/95 p-5 glass-strong shadow-glow"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <span className="font-mono text-2xs uppercase tracking-[0.3em] text-accent/80">
            ▸ link entity to mission
          </span>
          <button
            onClick={onClose}
            aria-label="Close"
            className="font-mono text-2xs text-mute2 hover:text-accent"
          >
            ✕
          </button>
        </div>

        <h2 className="mt-2 text-lg font-semibold text-inkhi">
          Link existing entity
        </h2>
        <p className="mt-1 text-xs text-mute2">
          Attach an investor, program, supplier, market opportunity, intel
          signal, or other CRM entity to this mission. Linking does not move
          the entity — it remains in its domain table and can be linked to
          multiple missions.
        </p>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (valid) mutation.mutate();
          }}
          className="mt-4 flex flex-col gap-3"
        >
          <label className="flex flex-col gap-1">
            <span className="font-mono text-2xs uppercase tracking-widest text-mute2">
              entity type
            </span>
            <select
              value={entityType}
              onChange={(e) => setEntityType(e.target.value)}
              className="rounded-md border border-border bg-bgdeep px-3 py-2 text-sm text-ink outline-none focus:border-accent"
            >
              {ENTITY_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label} ({t.value})
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1">
            <span className="font-mono text-2xs uppercase tracking-widest text-mute2">
              entity id
            </span>
            <input
              value={entityId}
              onChange={(e) => setEntityId(e.target.value.replace(/[^0-9]/g, ""))}
              required
              placeholder="42"
              className="rounded-md border border-border bg-bgdeep px-3 py-2 font-mono text-sm text-inkhi outline-none focus:border-accent"
            />
            <span className="font-mono text-[10px] text-mute2">
              numeric ID from the entity's domain table
            </span>
          </label>

          <label className="flex flex-col gap-1">
            <span className="font-mono text-2xs uppercase tracking-widest text-mute2">
              relationship
            </span>
            <select
              value={relationship}
              onChange={(e) => setRelationship(e.target.value)}
              className="rounded-md border border-border bg-bgdeep px-3 py-2 text-sm text-ink outline-none focus:border-accent"
            >
              {RELATIONSHIP_TYPES.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1">
            <span className="font-mono text-2xs uppercase tracking-widest text-mute2">
              notes (optional)
            </span>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              className="rounded-md border border-border bg-bgdeep px-3 py-2 text-sm text-ink outline-none focus:border-accent"
            />
          </label>

          {error && (
            <div className="rounded-md border border-red/40 bg-red/10 px-3 py-2 font-mono text-2xs text-red">
              {error}
            </div>
          )}

          <div className="flex items-center justify-end gap-2 border-t border-border/60 pt-3">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-border px-3 py-2 text-xs text-mute2 hover:border-border2 hover:text-ink"
            >
              cancel
            </button>
            <button
              type="submit"
              disabled={!valid || mutation.isPending}
              className="chip-accent rounded-md px-4 py-2 text-xs font-semibold uppercase tracking-widest hover:bg-accent/30 disabled:opacity-50"
            >
              {mutation.isPending ? "linking…" : "link entity"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
