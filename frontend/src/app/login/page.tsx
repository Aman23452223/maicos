"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";

export default function LoginPage() {
  const router = useRouter();
  const { user, status, signInWithPassword, signUp, signInWithOtp, signOut } = useAuth();
  const [mode, setMode] = useState<"signin" | "signup" | "magic">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  if (status === "loading") {
    return (
      <div className="min-h-screen flex items-center justify-center text-xs text-muted font-mono">
        Verifying cryptographic session…
      </div>
    );
  }

  if (user) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6 bg-[#08090b]">
        <div className="w-full max-w-md p-8 rounded-2xl bg-[#0e1217] border border-white/[0.08] shadow-2xl text-center space-y-4">
          <div className="w-14 h-14 mx-auto rounded-full bg-ok/10 border border-ok/20 flex items-center justify-center text-2xl text-ok">
            ✓
          </div>
          <h1 className="text-xl font-bold text-ink">Authenticated Session Active</h1>
          <p className="text-xs text-muted">
            Signed in as <strong className="text-ink font-mono">{user.email}</strong>
          </p>
          <div className="flex flex-col gap-2 pt-2">
            <button
              onClick={() => router.push("/command")}
              className="w-full py-2.5 rounded-xl bg-accent hover:bg-accent/90 text-bg font-semibold text-xs transition-all shadow-[0_0_15px_rgba(91,141,239,0.3)]"
            >
              Open AI Command Center
            </button>
            <button
              onClick={signOut}
              className="w-full py-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-muted hover:text-ink border border-white/10 text-xs font-medium transition-all"
            >
              Sign Out
            </button>
          </div>
        </div>
      </div>
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    setMsg(null);

    const cleanEmail = email.trim().toLowerCase();
    if (!cleanEmail || !cleanEmail.includes("@")) {
      setErr("Please enter a valid email address");
      setBusy(false);
      return;
    }

    try {
      if (mode === "signin") {
        await signInWithPassword(cleanEmail, password);
        router.push("/command");
      } else if (mode === "signup") {
        await signUp(cleanEmail, password, name.trim() || undefined);
        router.push("/command");
      } else if (mode === "magic") {
        await signInWithOtp(cleanEmail);
        setMsg("Magic link sent! Check your inbox.");
      }
    } catch (e) {
      setErr((e as Error).message || "Authentication failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6 bg-[#08090b] relative overflow-hidden">
      {/* Background ambient glow */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-96 h-96 bg-accent/10 rounded-full blur-3xl pointer-events-none" />

      {/* Brand */}
      <Link href="/" className="mb-8 flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-accent via-blue-600 to-purple-600 flex items-center justify-center text-white font-bold text-lg shadow-[0_0_20px_rgba(91,141,239,0.35)]">
          M
        </div>
        <div className="text-xl font-bold tracking-wider text-ink flex items-center gap-1.5">
          <span>MAICOS</span>
          <span className="text-[10px] px-1.5 py-0.2 rounded bg-accent/20 text-accent font-mono">
            OS
          </span>
        </div>
      </Link>

      <div className="w-full max-w-md p-8 rounded-2xl bg-[#0e1217]/90 backdrop-blur-xl border border-white/[0.08] shadow-2xl relative z-10">
        <div className="mb-6">
          <h1 className="text-xl font-bold text-ink tracking-tight">
            {mode === "signin"
              ? "Sign In to Workspace"
              : mode === "signup"
              ? "Create your AI Workspace"
              : "Sign In with Magic Link"}
          </h1>
          <p className="text-xs text-muted mt-1">
            Access your autonomous workforce, workflows, and operations.
          </p>
        </div>

        {/* Tab switcher */}
        <div className="flex rounded-lg bg-black/40 p-1 border border-white/5 mb-5 text-xs font-medium">
          <button
            type="button"
            onClick={() => {
              setMode("signin");
              setErr(null);
            }}
            className={`flex-1 py-1.5 rounded-md transition-all ${
              mode === "signin"
                ? "bg-panel text-ink shadow-sm font-semibold border border-white/10"
                : "text-muted hover:text-ink"
            }`}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => {
              setMode("signup");
              setErr(null);
            }}
            className={`flex-1 py-1.5 rounded-md transition-all ${
              mode === "signup"
                ? "bg-panel text-ink shadow-sm font-semibold border border-white/10"
                : "text-muted hover:text-ink"
            }`}
          >
            Create Account
          </button>
          <button
            type="button"
            onClick={() => {
              setMode("magic");
              setErr(null);
            }}
            className={`flex-1 py-1.5 rounded-md transition-all ${
              mode === "magic"
                ? "bg-panel text-ink shadow-sm font-semibold border border-white/10"
                : "text-muted hover:text-ink"
            }`}
          >
            Magic Link
          </button>
        </div>

        {/* Error notification banner */}
        {err && (
          <div className="mb-4 p-3 rounded-lg bg-bad/10 border border-bad/30 text-bad text-xs">
            {err}
          </div>
        )}

        {/* Success message banner */}
        {msg && (
          <div className="mb-4 p-3 rounded-lg bg-ok/10 border border-ok/30 text-ok text-xs">
            ✓ {msg}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-3.5">
          {mode === "signup" && (
            <div>
              <label className="block text-xs font-medium text-muted mb-1">
                Full Name
              </label>
              <input
                type="text"
                placeholder="Aman Chawhan"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-xs text-ink focus:outline-none focus:border-accent"
              />
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-muted mb-1">
              Email Address
            </label>
            <input
              type="email"
              placeholder="you@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-xs text-ink focus:outline-none focus:border-accent"
            />
          </div>

          {mode !== "magic" && (
            <div>
              <label className="block text-xs font-medium text-muted mb-1">
                Password
              </label>
              <input
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-xs text-ink focus:outline-none focus:border-accent"
              />
            </div>
          )}

          <button
            type="submit"
            disabled={busy}
            className="w-full mt-2 py-2.5 rounded-xl bg-accent hover:bg-accent/90 text-bg font-semibold text-xs transition-all shadow-[0_0_15px_rgba(91,141,239,0.3)] disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {busy ? (
              <>
                <span className="w-3.5 h-3.5 border-2 border-bg border-t-transparent rounded-full animate-spin" />
                <span>Authenticating…</span>
              </>
            ) : mode === "signin" ? (
              "Sign In to Workspace"
            ) : mode === "signup" ? (
              "Create Workspace Account"
            ) : (
              "Send Magic Link"
            )}
          </button>
        </form>

        <div className="mt-6 pt-4 border-t border-white/5 text-center text-xs text-muted">
          <Link href="/" className="hover:text-ink transition-colors">
            ← Back to Homepage
          </Link>
        </div>
      </div>
    </div>
  );
}