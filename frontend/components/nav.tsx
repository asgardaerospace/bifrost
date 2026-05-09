"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  { href: "/horizon", label: "Horizon", group: "command" },
  { href: "/topology", label: "Topology", group: "command" },
  { href: "/timeline", label: "Timeline", group: "command" },
  { href: "/missions", label: "Missions", group: "command" },
  { href: "/agents", label: "Agents", group: "command" },
  { href: "/executive", label: "Executive", group: "ops" },
  { href: "/dashboard", label: "Dashboard", group: "ops" },
  { href: "/console", label: "Command Console", group: "ops" },
  { href: "/engine", label: "Investor Engine", group: "ops" },
  { href: "/market", label: "Market", group: "ops" },
  { href: "/programs", label: "Programs", group: "ops" },
  { href: "/suppliers", label: "Suppliers", group: "ops" },
  { href: "/intel", label: "Intelligence", group: "ops" },
  { href: "/approvals", label: "Approvals", group: "ops" },
  { href: "/engine-writes", label: "Engine Writes", group: "ops" },
  { href: "/create", label: "Create", group: "ops" },
];

function renderItem(
  it: { href: string; label: string },
  pathname: string | null,
) {
  const active = pathname?.startsWith(it.href);
  return (
    <Link
      key={it.href}
      href={it.href}
      className={
        "rounded-md px-3 py-2 text-sm transition-colors " +
        (active
          ? "bg-border text-ink"
          : "text-muted hover:bg-border hover:text-ink")
      }
    >
      {it.label}
    </Link>
  );
}

export function Nav() {
  const pathname = usePathname();
  return (
    <aside className="w-56 shrink-0 border-r border-border bg-panel px-4 py-6">
      <div className="mb-8">
        <div className="font-mono text-xs uppercase tracking-widest text-muted">
          Asgard
        </div>
        <div className="mt-1 text-lg font-semibold">Bifrost</div>
      </div>
      <nav className="flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <div className="px-2 pb-1 font-mono text-[10px] uppercase tracking-widest text-muted/70">
            command
          </div>
          {items
            .filter((it) => it.group === "command")
            .map((it) => renderItem(it, pathname))}
        </div>
        <div className="flex flex-col gap-1">
          <div className="px-2 pb-1 font-mono text-[10px] uppercase tracking-widest text-muted/70">
            operations
          </div>
          {items
            .filter((it) => it.group === "ops")
            .map((it) => renderItem(it, pathname))}
        </div>
      </nav>
      <div className="absolute bottom-4 left-4 font-mono text-[10px] uppercase tracking-widest text-muted">
        Sprint 7 · internal
      </div>
    </aside>
  );
}
