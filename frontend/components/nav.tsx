"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  { href: "/executive", label: "Executive" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/console", label: "Command Console" },
  { href: "/engine", label: "Investor Engine" },
  { href: "/market", label: "Market" },
  { href: "/programs", label: "Programs" },
  { href: "/suppliers", label: "Suppliers" },
  { href: "/approvals", label: "Approvals" },
  { href: "/engine-writes", label: "Engine Writes" },
  { href: "/create", label: "Create" },
];

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
      <nav className="flex flex-col gap-1">
        {items.map((it) => {
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
        })}
      </nav>
      <div className="absolute bottom-4 left-4 font-mono text-[10px] uppercase tracking-widest text-muted">
        Phase 1 · internal
      </div>
    </aside>
  );
}
