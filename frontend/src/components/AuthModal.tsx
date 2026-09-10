"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";

export function AuthModal() {
  const {
    isAuthModalOpen,
    closeAuthModal,
    authModalMode,
    signInWithPassword,
    signUp,
    signInWithOtp,
  } = useAuth();

  const [mode, setMode] = useState<"signin" | "signup" | "magic">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  useEffect(() => {
    if (authModalMode === "signup") {
      setMode("signup");
    } else {
      setMode("signin");
    }
    setErr(null);
    setSuccessMsg(null);
  }, [authModalMode, isAuthModalOpen]);

  // Handle ESC key to close
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeAuthModal();
    };
    if (isAuthModalOpen) window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isAuthModalOpen, closeAuthModal]);

  if (!isAuthModalOpen) return null;

  const isValidEmail = email.trim().includes("@") && email.trim().includes(".");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setSuccessMsg(null);

    const cleanEmail = email.trim().toLowerCase();
    if (!cleanEmail || !cleanEmail.includes("@")) {
      setErr("Please enter a valid email address.");
      return;
    }

    if (mode !== "magic" && (!password || password.length < 6)) {
      setErr("Password must be at least 6 characters.");
      return;
    }

    setLoading(true);

    try {
      if (mode === "signin") {
        await signInWithPassword(cleanEmail, password);
        closeAuthModal();
      } else if (mode === "signup") {
        await signUp(cleanEmail, password, name.trim() || undefined);
        closeAuthModal();
      } else if (mode === "magic") {
        await signInWithOtp(cleanEmail);
        setSuccessMsg("Magic link sent! Check your email inbox.");
      }
    } catch (e) {
      setErr((e as Error).message || "Authentication failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md animate-fade-in">
      {/* Backdrop click handler */}
      <div className="absolute inset-0" onClick={closeAuthModal} />

      <div className="relative w-full max-w-md bg-[#0e1217] border border-white/10 rounded-2xl p-6 shadow-2xl z-10 text-ink">
        {/* Close button */}
        <button
          onClick={closeAuthModal}
          className="absolute top-4 right-4 text-muted hover:text-ink transition-colors text-lg p-1 rounded-md"
          aria-label="Close"
        >
          ✕
        </button>

        {/* Header */}
        <div className="mb-6">
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-accent/10 border border-accent/20 text-accent text-xs font-semibold uppercase tracking-wider mb-2">
            <span className="w-2 h-2 rounded-full bg-accent animate-pulse" />
            MAICOS Security
          </div>
          <h2 className="text-xl font-semibold tracking-tight">
            {mode === "signin"
              ? "Sign in to your Workspace"
              : mode === "signup"
              ? "Create your AI Workspace"
              : "Sign in with Magic Link"}
          </h2>
          <p className="text-xs text-muted mt-1">
            Access autonomous agents, real-time approval pipelines & operations.
          </p>
        </div>

        {/* Mode switcher tabs */}
        <div className="flex rounded-lg bg-black/40 p-1 border border-white/5 mb-4 text-xs font-medium">
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
          <div className="mb-4 p-3 rounded-lg bg-bad/10 border border-bad/30 text-bad text-xs flex items-start gap-2">
            <span className="font-bold">Error:</span>
            <span className="flex-1">{err}</span>
          </div>
        )}

        {/* Success notification banner */}
        {successMsg && (
          <div className="mb-4 p-3 rounded-lg bg-ok/10 border border-ok/30 text-ok text-xs flex items-start gap-2">
            <span className="font-bold">✓</span>
            <span className="flex-1">{successMsg}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="flex flex-col gap-3.5">
          {mode === "signup" && (
            <div>
              <label className="block text-xs font-medium text-muted mb-1">
                Your Full Name (optional)
              </label>
              <input
                type="text"
                placeholder="Aman Chawhan"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full bg-white/[0.04] border border-white/10 rounded-lg px-3 py-2 text-sm text-ink focus:outline-none focus:border-accent transition-colors"
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
              className="w-full bg-white/[0.04] border border-white/10 rounded-lg px-3 py-2 text-sm text-ink focus:outline-none focus:border-accent transition-colors"
            />
          </div>

          {mode !== "magic" && (
            <div>
              <div className="flex justify-between items-center mb-1">
                <label className="block text-xs font-medium text-muted">
                  Password
                </label>
                {mode === "signin" && (
                  <button
                    type="button"
                    onClick={() => setMode("magic")}
                    className="text-[11px] text-muted hover:text-accent transition-colors"
                  >
                    Forgot password?
                  </button>
                )}
              </div>
              <input
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full bg-white/[0.04] border border-white/10 rounded-lg px-3 py-2 text-sm text-ink focus:outline-none focus:border-accent transition-colors"
              />
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !isValidEmail}
            className={`w-full mt-2 py-2.5 px-4 rounded-lg font-medium text-sm transition-all flex items-center justify-center gap-2 ${
              loading || !isValidEmail
                ? "bg-white/10 text-muted cursor-not-allowed border border-white/5"
                : "bg-accent hover:bg-accent/90 text-bg shadow-[0_0_15px_rgba(91,141,239,0.3)] hover:shadow-[0_0_20px_rgba(91,141,239,0.5)] font-semibold"
            }`}
          >
            {loading ? (
              <>
                <span className="w-4 h-4 border-2 border-bg border-t-transparent rounded-full animate-spin" />
                <span>Processing…</span>
              </>
            ) : mode === "signin" ? (
              "Sign In to Workspace"
            ) : mode === "signup" ? (
              "Create Workspace & Continue"
            ) : (
              "Send Magic Link"
            )}
          </button>
        </form>

        {/* Footer info */}
        <div className="mt-5 pt-4 border-t border-white/5 text-center text-xs text-muted">
          {mode === "signin" ? (
            <span>
              Don't have a workspace yet?{" "}
              <button
                type="button"
                onClick={() => {
                  setMode("signup");
                  setErr(null);
                }}
                className="text-accent hover:underline font-medium"
              >
                Create one in seconds
              </button>
            </span>
          ) : (
            <span>
              Already have an account?{" "}
              <button
                type="button"
                onClick={() => {
                  setMode("signin");
                  setErr(null);
                }}
                className="text-accent hover:underline font-medium"
              >
                Sign in here
              </button>
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
