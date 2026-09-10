"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";

const ROUTE_NAMES: Record<string, { title: string; subtitle: string; icon: string }> = {
  "/": { title: "Overview", subtitle: "Workspace Dashboard", icon: "📊" },
  "/command": { title: "Command Center", subtitle: "Natural Language Task Delegation", icon: "⚡" },
  "/workflows": { title: "Workflows", subtitle: "Autonomous Execution Pipeline", icon: "🔁" },
  "/approvals": { title: "Approval Center", subtitle: "Human-in-the-Loop Decisions", icon: "🛡️" },
  "/agents": { title: "AI Workforce", subtitle: "11 Autonomous Specialized Agents", icon: "🤖" },
  "/integrations": { title: "Integrations", subtitle: "External APIs & Connectors", icon: "🔌" },
  "/knowledge": { title: "Knowledge Vault", subtitle: "Vector & RAG Indexing", icon: "📚" },
  "/audit": { title: "Audit Trail", subtitle: "Immutable Action Log & Compliance", icon: "📜" },
  "/settings": { title: "Settings", subtitle: "LLM Providers & Workspace Config", icon: "⚙️" },
};

export function AppHeader() {
  const pathname = usePathname();
  const { user, status, signOut, openAuthModal } = useAuth();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [systemPing, setSystemPing] = useState<"ok" | "checking" | "down">("checking");
  const dropdownRef = useRef<HTMLDivElement>(null);

  const routeInfo = ROUTE_NAMES[pathname] || {
    title: pathname.replace("/", "").toUpperCase() || "Dashboard",
    subtitle: "Operations",
    icon: "🧭",
  };

  // Check live backend health
  useEffect(() => {
    let mounted = true;
    async function checkHealth() {
      try {
        const res = await fetch("/api/health", { cache: "no-store" });
        if (mounted) {
          setSystemPing(res.ok ? "ok" : "down");
        }
      } catch {
        if (mounted) setSystemPing("down");
      }
    }
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <header className="h-16 border-b border-white/[0.08] bg-[#090b0e]/80 backdrop-blur-xl px-6 flex items-center justify-between z-30 sticky top-0">
      {/* Left: Breadcrumb / Route Info */}
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-white/[0.04] border border-white/10 flex items-center justify-center text-base shadow-sm">
          {routeInfo.icon}
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-muted uppercase tracking-wider">MAICOS</span>
            <span className="text-xs text-muted/40">/</span>
            <span className="text-sm font-semibold text-ink tracking-tight">{routeInfo.title}</span>
          </div>
          <p className="text-[11px] text-muted hidden sm:block">{routeInfo.subtitle}</p>
        </div>
      </div>

      {/* Right: Status Pill & Auth Controls */}
      <div className="flex items-center gap-3.5">
        {/* Backend Connectivity Status */}
        <div
          className="hidden md:flex items-center gap-2 px-3 py-1 rounded-full bg-white/[0.03] border border-white/[0.07] text-xs text-muted"
          title={systemPing === "ok" ? "Railway Backend Live" : "Checking Backend Connection"}
        >
          <span
            className={`w-2 h-2 rounded-full ${
              systemPing === "ok"
                ? "bg-ok shadow-[0_0_8px_rgba(63,185,80,0.6)] animate-pulse"
                : systemPing === "down"
                ? "bg-bad"
                : "bg-warn animate-pulse"
            }`}
          />
          <span className="text-[11px] font-medium tracking-wide">
            {systemPing === "ok" ? "Railway Live" : systemPing === "down" ? "Offline" : "Connecting…"}
          </span>
        </div>

        {/* Quick Action Button */}
        {pathname !== "/command" && (
          <Link
            href="/command"
            className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent/10 border border-accent/25 text-accent hover:bg-accent/20 transition-all text-xs font-medium"
          >
            <span>⚡</span>
            <span>New Command</span>
          </Link>
        )}

        {/* Auth State Management */}
        {status === "loading" ? (
          <div className="w-8 h-8 rounded-full bg-white/5 animate-pulse border border-white/10" />
        ) : user ? (
          /* Authenticated User Menu */
          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => setDropdownOpen(!dropdownOpen)}
              className="flex items-center gap-2.5 p-1.5 pr-3 rounded-full bg-white/[0.04] hover:bg-white/[0.08] border border-white/10 transition-all"
            >
              <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-accent/80 to-blue-400 text-bg flex items-center justify-center font-bold text-xs uppercase shadow-sm">
                {user.name ? user.name.charAt(0) : user.email.charAt(0)}
              </div>
              <div className="text-left hidden sm:block">
                <div className="text-xs font-medium text-ink max-w-[130px] truncate">
                  {user.name || user.email.split("@")[0]}
                </div>
                <div className="text-[10px] text-accent leading-none font-mono">
                  {user.roles?.[0] || "admin"}
                </div>
              </div>
              <span className="text-xs text-muted">▾</span>
            </button>

            {/* Dropdown Menu */}
            {dropdownOpen && (
              <div className="absolute right-0 mt-2 w-64 rounded-xl bg-[#0e1217] border border-white/10 p-2 shadow-2xl z-50 text-xs animate-fade-in">
                <div className="p-2.5 border-b border-white/5 mb-1">
                  <p className="font-semibold text-ink truncate">{user.name || "Workspace Admin"}</p>
                  <p className="text-muted text-[11px] truncate">{user.email}</p>
                  <div className="mt-1.5 inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-accent/10 border border-accent/20 text-[10px] text-accent font-mono">
                    Roles: {user.roles?.join(", ") || "admin, owner"}
                  </div>
                </div>

                <Link
                  href="/settings"
                  onClick={() => setDropdownOpen(false)}
                  className="flex items-center gap-2 px-3 py-2 rounded-lg text-muted hover:text-ink hover:bg-white/5 transition-colors"
                >
                  <span>⚙️</span>
                  <span>Settings & API Keys</span>
                </Link>

                <Link
                  href="/audit"
                  onClick={() => setDropdownOpen(false)}
                  className="flex items-center gap-2 px-3 py-2 rounded-lg text-muted hover:text-ink hover:bg-white/5 transition-colors"
                >
                  <span>📜</span>
                  <span>Security Audit Log</span>
                </Link>

                <div className="border-t border-white/5 my-1" />

                <button
                  onClick={async () => {
                    setDropdownOpen(false);
                    await signOut();
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-bad hover:bg-bad/10 transition-colors text-left"
                >
                  <span>🚪</span>
                  <span>Sign Out</span>
                </button>
              </div>
            )}
          </div>
        ) : (
          /* Unauthenticated State */
          <div className="flex items-center gap-2">
            <button
              onClick={() => openAuthModal("signin")}
              className="px-3.5 py-1.5 rounded-lg text-xs font-medium text-ink hover:bg-white/5 border border-white/10 transition-all"
            >
              Sign In
            </button>
            <button
              onClick={() => openAuthModal("signup")}
              className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-accent hover:bg-accent/90 text-bg shadow-[0_0_12px_rgba(91,141,239,0.3)] transition-all"
            >
              Get Started
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
