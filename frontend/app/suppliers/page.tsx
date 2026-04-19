"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { SupplierRead } from "@/types/api";
import { Empty, Panel, Pill, Stat } from "@/components/ui";

function tone(
  status: string,
): "default" | "warn" | "danger" | "ok" | "accent" {
  switch (status) {
    case "onboarded":
      return "ok";
    case "qualified":
      return "accent";
    case "contacted":
      return "warn";
    default:
      return "default";
  }
}

function SupplierRows({ rows }: { rows: SupplierRead[] }) {
  if (rows.length === 0) return <Empty>No suppliers.</Empty>;
  return (
    <ul className="divide-y divide-border">
      {rows.map((s) => (
        <li key={s.id} className="flex items-start justify-between py-2">
          <div className="min-w-0">
            <div className="truncate font-medium">{s.name}</div>
            <div className="text-xs text-muted">
              {[s.type, s.region, s.country].filter(Boolean).join(" · ") || "—"}
            </div>
          </div>
          <div className="flex flex-col items-end gap-1">
            <Pill tone={tone(s.onboarding_status)}>{s.onboarding_status}</Pill>
            {s.preferred_partner_score != null && (
              <span className="text-[11px] text-muted tabular-nums">
                p{s.preferred_partner_score}
              </span>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}

export default function SuppliersPage() {
  const summary = useQuery({
    queryKey: ["supplier-onboarding"],
    queryFn: api.onboardingSummary,
  });
  const all = useQuery({
    queryKey: ["suppliers-all"],
    queryFn: () => api.listSuppliers({ limit: 200 }),
  });
  const qualified = useQuery({
    queryKey: ["suppliers-qualified"],
    queryFn: () => api.listQualifiedSuppliers(50),
  });
  const byCapability = useQuery({
    queryKey: ["suppliers-by-capability"],
    queryFn: api.suppliersByCapability,
  });

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-xl font-semibold">Suppliers</h1>
        <p className="mt-1 text-sm text-muted">
          Manufacturing and partner network — the capability that programs
          draw on to deliver.
        </p>
      </header>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Total" value={summary.data?.total ?? "—"} />
        <Stat label="Qualified" value={summary.data?.qualified ?? "—"} />
        <Stat label="Onboarded" value={summary.data?.onboarded ?? "—"} />
        <Stat
          label="On active programs"
          value={summary.data?.active_program_supplier_count ?? "—"}
        />
      </div>

      <Panel title="Onboarding pipeline">
        {summary.isLoading ? (
          <Empty>Loading…</Empty>
        ) : !summary.data ||
          Object.keys(summary.data.by_status).length === 0 ? (
          <Empty>No suppliers yet.</Empty>
        ) : (
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            {Object.entries(summary.data.by_status).map(([k, v]) => (
              <div
                key={k}
                className="rounded border border-border bg-bg/40 px-3 py-2"
              >
                <div className="font-mono text-[10px] uppercase tracking-widest text-muted">
                  {k}
                </div>
                <div className="text-lg tabular-nums">{v}</div>
              </div>
            ))}
          </div>
        )}
      </Panel>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Panel title="All suppliers">
          {all.isLoading ? <Empty>Loading…</Empty> : <SupplierRows rows={all.data ?? []} />}
        </Panel>

        <Panel title="Qualified / onboarded">
          {qualified.isLoading ? (
            <Empty>Loading…</Empty>
          ) : (
            <SupplierRows rows={qualified.data ?? []} />
          )}
        </Panel>
      </div>

      <Panel title="By capability">
        {byCapability.isLoading ? (
          <Empty>Loading…</Empty>
        ) : !byCapability.data ||
          Object.keys(byCapability.data).length === 0 ? (
          <Empty>No capabilities recorded.</Empty>
        ) : (
          <div className="space-y-3">
            {Object.entries(byCapability.data).map(([cap, rows]) => (
              <div key={cap} className="rounded border border-border bg-bg/40">
                <div className="border-b border-border px-3 py-2 font-mono text-[11px] uppercase tracking-widest text-muted">
                  {cap} · {rows.length}
                </div>
                <div className="px-3">
                  <SupplierRows rows={rows} />
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
