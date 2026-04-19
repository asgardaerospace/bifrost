import type { SupplierListOutput, SupplierRow } from "@/types/api";
import { Empty, Pill } from "@/components/ui";

function statusTone(
  status: string,
): "default" | "warn" | "danger" | "ok" | "accent" {
  switch (status) {
    case "onboarded":
      return "ok";
    case "qualified":
      return "accent";
    case "contacted":
      return "warn";
    case "identified":
    default:
      return "default";
  }
}

function Row({ s }: { s: SupplierRow }) {
  return (
    <li className="flex items-start justify-between gap-3 py-2">
      <div className="min-w-0">
        <div className="truncate font-medium">{s.name}</div>
        <div className="text-xs text-muted">
          {[s.type, s.region, s.country].filter(Boolean).join(" · ") || "—"}
        </div>
        {(s.capabilities.length > 0 || s.certifications.length > 0) && (
          <div className="mt-1 flex flex-wrap gap-1">
            {s.capabilities.map((c) => (
              <Pill key={`cap-${c}`} tone="default">{c}</Pill>
            ))}
            {s.certifications.map((c) => (
              <Pill key={`cert-${c}`} tone="accent">{c}</Pill>
            ))}
          </div>
        )}
      </div>
      <div className="flex flex-col items-end gap-1">
        <Pill tone={statusTone(s.onboarding_status)}>
          {s.onboarding_status}
        </Pill>
        {s.preferred_partner_score != null && (
          <span className="text-[11px] text-muted tabular-nums">
            p{s.preferred_partner_score}
          </span>
        )}
      </div>
    </li>
  );
}

export function SupplierListOutputView({
  output,
}: {
  output: SupplierListOutput;
}) {
  const { kind } = output;
  return (
    <div className="space-y-3">
      <header>
        <h3 className="font-semibold">{output.headline}</h3>
        {output.rationale && (
          <p className="text-xs text-muted">{output.rationale}</p>
        )}
      </header>

      {(kind === "all" || kind === "qualified") && (
        <ul className="divide-y divide-border">
          {output.suppliers.length === 0 ? (
            <Empty>No suppliers.</Empty>
          ) : (
            output.suppliers.map((s) => <Row key={s.id} s={s} />)
          )}
        </ul>
      )}

      {kind === "by_capability" && (
        <div className="space-y-3">
          {Object.entries(output.by_capability).map(([cap, rows]) => (
            <div key={cap} className="rounded border border-border bg-bg/40">
              <div className="border-b border-border px-3 py-2 font-mono text-[11px] uppercase tracking-widest text-muted">
                {cap} · {rows.length}
              </div>
              <ul className="divide-y divide-border px-3">
                {rows.map((s) => (
                  <Row key={s.id} s={s} />
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      {kind === "for_program" && (
        <ul className="divide-y divide-border">
          {output.program_links.length === 0 ? (
            <Empty>No suppliers linked to this program.</Empty>
          ) : (
            output.program_links.map((l) => (
              <li
                key={l.link_id}
                className="flex items-start justify-between py-2"
              >
                <div className="min-w-0">
                  <div className="truncate font-medium">
                    {l.supplier_name ?? `supplier #${l.supplier_id}`}
                  </div>
                  <div className="text-xs text-muted">
                    {l.program_name ?? `program #${l.program_id}`} · {l.role}
                  </div>
                </div>
                <Pill
                  tone={
                    l.status === "confirmed"
                      ? "ok"
                      : l.status === "engaged"
                        ? "accent"
                        : "warn"
                  }
                >
                  {l.status}
                </Pill>
              </li>
            ))
          )}
        </ul>
      )}

      {kind === "onboarding" && (
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          {Object.entries(output.counts)
            .filter(([k]) => k.startsWith("status."))
            .map(([k, v]) => (
              <div
                key={k}
                className="rounded border border-border bg-bg/40 px-3 py-2"
              >
                <div className="font-mono text-[10px] uppercase tracking-widest text-muted">
                  {k.replace("status.", "")}
                </div>
                <div className="text-lg tabular-nums">{v}</div>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}
