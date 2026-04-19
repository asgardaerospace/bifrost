"use client";

export function fmtDate(iso?: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      month: "short",
      day: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function fmtRelative(iso?: string | null): string {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return iso;
  const diffMs = t - Date.now();
  const abs = Math.abs(diffMs);
  const mins = Math.round(abs / 60000);
  const hrs = Math.round(mins / 60);
  const days = Math.round(hrs / 24);
  let val: string;
  if (mins < 60) val = `${mins}m`;
  else if (hrs < 48) val = `${hrs}h`;
  else val = `${days}d`;
  return diffMs < 0 ? `${val} ago` : `in ${val}`;
}

export function StatusDot({
  tone,
}: {
  tone: "red" | "amber" | "green" | "blue" | "muted";
}) {
  const bg =
    tone === "red"
      ? "bg-red"
      : tone === "amber"
      ? "bg-amber"
      : tone === "green"
      ? "bg-green"
      : tone === "blue"
      ? "bg-blue"
      : "bg-mute2";
  return <span className={`inline-block h-1.5 w-1.5 rounded-full ${bg}`} />;
}

export function SeverityChip({
  severity,
}: {
  severity: "info" | "warn" | "critical";
}) {
  const cls =
    severity === "critical"
      ? "border-red text-red"
      : severity === "warn"
      ? "border-amber text-amber"
      : "border-blue text-blue";
  return (
    <span
      className={`inline-flex items-center rounded-sm border bg-transparent px-1.5 py-0.5 text-2xs font-mono uppercase tracking-wider ${cls}`}
    >
      {severity}
    </span>
  );
}

export function DomainChip({ domain }: { domain: string }) {
  return <span className="chip">{domain}</span>;
}
