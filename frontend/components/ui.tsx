import type { ReactNode } from "react";

export function Panel({
  title,
  right,
  children,
}: {
  title?: ReactNode;
  right?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="rounded-lg border border-border bg-panel">
      {(title || right) && (
        <header className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="font-mono text-xs uppercase tracking-widest text-muted">
            {title}
          </h2>
          {right}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Pill({
  children,
  tone = "default",
}: {
  children: ReactNode;
  tone?: "default" | "warn" | "danger" | "ok" | "accent";
}) {
  const classes: Record<string, string> = {
    default: "bg-border text-muted",
    warn: "bg-warn/15 text-warn",
    danger: "bg-danger/15 text-danger",
    ok: "bg-ok/15 text-ok",
    accent: "bg-accent/15 text-accent",
  };
  return (
    <span
      className={
        "inline-flex items-center rounded px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest " +
        classes[tone]
      }
    >
      {children}
    </span>
  );
}

export function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded-md border border-border bg-bg/40 px-4 py-3">
      <div className="font-mono text-[10px] uppercase tracking-widest text-muted">
        {label}
      </div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="py-6 text-center text-sm text-muted">{children}</div>
  );
}

/**
 * Badge identifying the source system of a record. Operators must
 * always be able to tell native Bifrost data from external investor
 * engine data — never render mixed lists without this.
 */
export function SourceBadge({
  source,
}: {
  source: "bifrost" | "investor_engine";
}) {
  if (source === "investor_engine") {
    return <Pill tone="accent">Investor Engine</Pill>;
  }
  return <Pill tone="default">Bifrost</Pill>;
}

export function formatDate(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function relative(iso?: string | null): string {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diff / 86_400_000);
  if (days < 1) {
    const hrs = Math.floor(diff / 3_600_000);
    if (hrs < 1) return "just now";
    return `${hrs}h ago`;
  }
  if (days < 30) return `${days}d ago`;
  return `${Math.floor(days / 30)}mo ago`;
}
