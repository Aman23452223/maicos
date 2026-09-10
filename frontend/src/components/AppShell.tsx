"use client";

import { usePathname } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { AppHeader } from "@/components/AppHeader";
import { AuthModal } from "@/components/AuthModal";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  // Standalone pages that don't use the dashboard chrome
  const isStandalone = pathname === "/" || pathname === "/login";

  if (isStandalone) {
    return (
      <>
        {children}
        <AuthModal />
      </>
    );
  }

  return (
    <div className="min-h-screen flex bg-[#08090b] text-ink selection:bg-accent/30 selection:text-white">
      {/* Sidebar navigation */}
      <Sidebar />

      {/* Main Dashboard Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-x-hidden">
        <AppHeader />
        <main className="flex-1 p-6 md:p-8 max-w-7xl w-full mx-auto animate-fade-in">
          {children}
        </main>
      </div>

      {/* Global Auth Modal */}
      <AuthModal />
    </div>
  );
}
