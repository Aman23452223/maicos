"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import useSWR from "swr";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

type NavItem = {
  href: string;
  label: string;
  icon: string;
  badgeKey?: "approvals";
};

const NAV_GROUPS: { title: string; items: NavItem[] }[] = [
  {
    title: "OPERATIONS",
    items: [
      { href: "/command", label: "AI Command Center", icon: "⚡" },
      { href: "/workflows", label: "Workflows", icon: "🔁" },
      { href: "/approvals", label: "Approvals", icon: "🛡️", badgeKey: "approvals" },
    ],
  },
  {
    title: "AI WORKFORCE",
    items: [
      { href: "/agents", label: "Agents (11 Active)", icon: "🤖" },
      { href: "/knowledge", label: "Knowledge Vault", icon: "📚" },
      { href: "/integrations", label: "Integrations", icon: "🔌" },
    ],
  },
  {
    title: "GOVERNANCE",
    items: [
      { href: "/audit", label: "Audit Trail", icon: "📜" },
      { href: "/settings", label: "System Settings", icon: "⚙️" },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuth();

  // Fetch pending approvals count if logged in
  const { data: approvals } = useSWR(
    user ? "pending-approvals-count" : null,
    () => api.listApprovals("PENDING"),
    { refreshInterval: 15000 }
  );

  const pendingCount = approvals?.length ?? 0;

  return (
    <aside className="w-64 border-r border-white/[0.08] bg-[#07080a] flex flex-col justify-between p-4 flex-shrink-0 z-20">
      <div>
        {/* Brand Header */}
        <Link href="/" className="flex items-center gap-3 px-2 py-3 mb-6 group">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-accent/80 via-blue-600 to-purple-600 flex items-center justify-center text-white font-bold text-lg shadow-[0_0_20px_rgba(91,141,239,0.35)] group-hover:shadow-[0_0_25px_rgba(91,141,239,0.5)] transition-all">
            M
          </div>
          <div>
            <div className="text-base font-bold tracking-wider text-ink flex items-center gap-1.5">
              <span>MAICOS</span>
              <span className="text-[10px] px-1.5 py-0.2 rounded bg-accent/20 text-accent font-mono">
                OS
              </span>
            </div>
            <div className="text-[11px] text-muted tracking-tight">Autonomous Workforce</div>
          </div>
        </Link>

        {/* Navigation Groups */}
        <div className="space-y-6">
          {NAV_GROUPS.map((group) => (
            <div key={group.title}>
              <div className="text-[10px] font-semibold text-muted/60 uppercase tracking-wider px-3 mb-1.5 font-mono">
                {group.title}
              </div>
              <nav className="space-y-0.5">
                {group.items.map((item) => {
                  const isActive = pathname === item.href;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={`flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-all ${
                        isActive
                          ? "bg-accent/15 text-white font-semibold border border-accent/25 shadow-[0_0_12px_rgba(91,141,239,0.15)]"
                          : "text-muted hover:text-ink hover:bg-white/[0.04]"
                      }`}
                    >
                      <div className="flex items-center gap-2.5">
                        <span className="text-sm">{item.icon}</span>
                        <span>{item.label}</span>
                      </div>

                      {/* Dynamic Badge for Pending Approvals */}
                      {item.badgeKey === "approvals" && pendingCount > 0 && (
                        <span className="px-1.5 py-0.5 rounded-full bg-warn/20 text-warn border border-warn/30 text-[10px] font-bold animate-pulse">
                          {pendingCount}
                        </span>
                      )}
                    </Link>
                  );
                })}
              </nav>
            </div>
          ))}
        </div>
      </div>

      {/* Sidebar Footer */}
      <div className="pt-4 border-t border-white/[0.07] mt-6">
        <div className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.06]">
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="text-muted text-[11px]">System Status</span>
            <span className="flex items-center gap-1.5 text-[11px] text-ok font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-ok animate-pulse" />
              Optimal
            </span>
          </div>
          <div className="text-[11px] text-muted/70 truncate">
            {user ? `Connected: ${user.email}` : "Mode: Guest Preview"}
          </div>
        </div>
      </div>
    </aside>
  );
}
