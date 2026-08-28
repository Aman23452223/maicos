"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/command", label: "AI Command Center" },
  { href: "/workflows", label: "Workflows" },
  { href: "/approvals", label: "Approvals" },
  { href: "/agents", label: "Agents" },
  { href: "/integrations", label: "Integrations" },
  { href: "/knowledge", label: "Knowledge" },
  { href: "/audit", label: "Audit" },
  { href: "/settings", label: "Settings" },
];

export function Sidebar() {
  const path = usePathname();
  return (
    <aside className="w-64 border-r border-line p-4 hidden md:flex md:flex-col gap-1">
      <div className="text-lg font-semibold mb-4">MAICOS</div>
      <div className="text-xs text-muted mb-4">AI workforce for company operations</div>
      <nav className="flex flex-col gap-1">
        {NAV.map((n) => (
          <Link
            key={n.href}
            href={n.href}
            className={`px-3 py-2 rounded-lg text-sm ${
              path === n.href ? "bg-panel text-ink" : "text-muted hover:text-ink"
            }`}
          >
            {n.label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
