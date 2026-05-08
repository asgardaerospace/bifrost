"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { SimulationResultRead } from "@/types/api";

type SimKind = "supplier_failure" | "approval_delay" | "dependency_propagation";

const KIND_LABEL: Record<SimKind, string> = {
  supplier_failure: "Supplier failure",
  approval_delay: "Approval delay",
  dependency_propagation: "Dependency propagation",
};

/**
 * Lightweight what-if analysis. Deterministic propagation, never speculative.
 */
export function SimulationPanel({ missionId }: { missionId?: number }) {
  const [kind, setKind] = useState<SimKind>("dependency_propagation");
  const [supplierId, setSupplierId] = useState("");
  const [approvalId, setApprovalId] = useState("");
  const [delayHours, setDelayHours] = useState("48");
  const [result, setResult] = useState<SimulationResultRead | null>(null);

  const mutation = useMutation({
    mutationFn: async () => {
      if (kind === "supplier_failure") {
        return api.simulateSupplierFailure(Number(supplierId));
      }
      if (kind === "approval_delay") {
        return api.simulateApprovalDelay(
          Number(approvalId),
          Number(delayHours),
        );
      }
      // dependency_propagation defaults to the open mission.
      const seedType = "mission";
      const seedId = missionId ?? Number(supplierId || 1);
      return api.simulateDependencyPropagation(seedType, seedId, 2);
    },
    onSuccess: (data) => setResult(data),
  });

  return (
    <section className="rounded-lg border border-border/60 bg-panel/60">
      <header className="flex items-center justify-between border-b border-border/60 px-4 py-3">
        <span className="font-mono text-2xs uppercase tracking-widest text-accent/80">
          ▸ what-if simulation
        </span>
        <div className="flex items-center gap-1">
          {(["supplier_failure", "approval_delay", "dependency_propagation"] as SimKind[]).map(
            (k) => (
              <button
                key={k}
                type="button"
                onClick={() => {
                  setKind(k);
                  setResult(null);
                }}
                className={
                  "rounded-md border px-2 py-1 font-mono text-[10px] uppercase tracking-widest transition-colors " +
                  (kind === k
                    ? "border-accent text-accent"
                    : "border-border/60 text-mute2 hover:border-accent/40 hover:text-accent")
                }
              >
                {KIND_LABEL[k]}
              </button>
            ),
          )}
        </div>
      </header>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          mutation.mutate();
        }}
        className="flex flex-wrap items-end gap-3 border-b border-border/60 p-3"
      >
        {kind === "supplier_failure" && (
          <label className="flex flex-col gap-1">
            <span className="font-mono text-[10px] uppercase tracking-widest text-mute2">
              supplier id
            </span>
            <input
              value={supplierId}
              onChange={(e) =>
                setSupplierId(e.target.value.replace(/[^0-9]/g, ""))
              }
              placeholder="42"
              className="w-24 rounded-md border border-border bg-bgdeep px-2 py-1 font-mono text-sm text-inkhi outline-none focus:border-accent"
            />
          </label>
        )}
        {kind === "approval_delay" && (
          <>
            <label className="flex flex-col gap-1">
              <span className="font-mono text-[10px] uppercase tracking-widest text-mute2">
                approval id
              </span>
              <input
                value={approvalId}
                onChange={(e) =>
                  setApprovalId(e.target.value.replace(/[^0-9]/g, ""))
                }
                placeholder="7"
                className="w-24 rounded-md border border-border bg-bgdeep px-2 py-1 font-mono text-sm text-inkhi outline-none focus:border-accent"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="font-mono text-[10px] uppercase tracking-widest text-mute2">
                delay (hours)
              </span>
              <input
                value={delayHours}
                onChange={(e) =>
                  setDelayHours(e.target.value.replace(/[^0-9]/g, ""))
                }
                className="w-24 rounded-md border border-border bg-bgdeep px-2 py-1 font-mono text-sm text-inkhi outline-none focus:border-accent"
              />
            </label>
          </>
        )}
        {kind === "dependency_propagation" && (
          <div className="font-mono text-2xs text-mute2">
            seed: mission #{missionId ?? "?"} · depth 2
          </div>
        )}
        <button
          type="submit"
          disabled={mutation.isPending}
          className="chip-accent rounded-md px-3 py-2 font-mono text-[10px] uppercase tracking-widest hover:bg-accent/30 disabled:opacity-50"
        >
          {mutation.isPending ? "running…" : "run"}
        </button>
      </form>

      <div className="px-4 py-3">
        {!result && !mutation.isPending && (
          <div className="font-mono text-2xs text-mute2">
            ▸ deterministic what-if propagation. assumptions surfaced inline.
            no forecasting.
          </div>
        )}
        {mutation.isPending && (
          <div className="animate-soft-pulse font-mono text-2xs text-mute2">
            ▸ propagating…
          </div>
        )}
        {result && (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-3 font-mono text-2xs uppercase tracking-wider text-mute2">
              <span className="text-accent/80">{result.simulation_type}</span>
              <span>conf {Math.round(result.confidence * 100)}%</span>
              <span>
                {result.impacted_missions.length} impacted ·{" "}
                {result.propagation_paths.length} edges
              </span>
            </div>
            {result.impacted_missions.length > 0 && (
              <ul className="flex flex-col gap-2">
                {result.impacted_missions.map((im) => (
                  <li
                    key={im.mission_id}
                    className="rounded-md border border-border/60 bg-panel2/40 p-2"
                  >
                    <div className="flex items-center justify-between font-mono text-2xs uppercase tracking-wider">
                      <span className="text-accent/80">{im.codename}</span>
                      <span
                        className={
                          im.pressure_delta >= 0 ? "text-red" : "text-green"
                        }
                      >
                        Δ pressure {im.pressure_delta >= 0 ? "+" : ""}
                        {im.pressure_delta}
                      </span>
                    </div>
                    <div className="mt-1 text-xs text-ink">{im.name}</div>
                    <div className="mt-1 text-xs text-mute2">{im.rationale}</div>
                  </li>
                ))}
              </ul>
            )}
            {result.assumptions.length > 0 && (
              <div className="border-t border-border/60 pt-2">
                <div className="mb-1 font-mono text-[10px] uppercase tracking-widest text-mute2">
                  assumptions
                </div>
                <ul className="space-y-0.5 text-xs text-mute2">
                  {result.assumptions.map((a, i) => (
                    <li key={i}>· {a}</li>
                  ))}
                </ul>
              </div>
            )}
            {result.notes.length > 0 && (
              <div className="border-t border-border/60 pt-2 font-mono text-2xs text-amber">
                {result.notes.map((n, i) => (
                  <div key={i}>▸ {n}</div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
