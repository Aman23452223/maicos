import "./globals.css";
import { SupabaseAuthProvider } from "@/contexts/AuthContext";
import { AppShell } from "@/components/AppShell";

export const metadata = {
  title: "MAICOS — Multi-Agent AI Company OS",
  description: "An AI workforce that runs your company operations.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#08090b] text-[#e8edf3] antialiased selection:bg-blue-500/30">
        <SupabaseAuthProvider>
          <AppShell>{children}</AppShell>
        </SupabaseAuthProvider>
      </body>
    </html>
  );
}
