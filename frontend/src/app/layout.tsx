import "./globals.css";
import { Sidebar } from "@/components/Sidebar";
import { Topbar } from "@/components/Topbar";

export const metadata = {
  title: "MAICOS — Multi-Agent AI Company OS",
  description: "An AI workforce that runs your company operations.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="min-h-screen flex">
          <Sidebar />
          <main className="flex-1 flex flex-col">
            <Topbar />
            <div className="p-6 flex-1">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
