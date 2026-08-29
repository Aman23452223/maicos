"use client";

import { useState } from "react";
import { useSupabaseAuth } from "@/contexts/AuthContext";

export default function LoginPage() {
  const auth = useSupabaseAuth();
  const [mode, setMode] = useState<"password" | "magic">("password");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  if (auth.status === "disabled") {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="card max-w-md w-full">
          <h1 className="text-lg font-semibold mb-2">Sign in</h1>
          <p className="text-sm text-muted">
            Supabase auth is not configured. Set
            <code className="mx-1">NEXT_PUBLIC_SUPABASE_URL</code>
            and
            <code className="mx-1">NEXT_PUBLIC_SUPABASE_ANON_KEY</code>
            in <code>frontend/.env.local</code>, then restart the dev server.
          </p>
        </div>
      </div>
    );
  }

  if (auth.status === "loading") {
    return (
      <div className="min-h-screen flex items-center justify-center text-sm text-muted">
        Loading session…
      </div>
    );
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      if (mode === "password") {
        await auth.signInWithPassword(email, password);
        setMsg("Signed in.");
      } else {
        await auth.signInWithOtp(email);
        setMsg("Check your inbox for the magic link.");
      }
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function signup() {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      await auth.signUp(email, password);
      setMsg("Account created. Check your email to confirm.");
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (auth.status === "authed") {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="card max-w-md w-full">
          <h1 className="text-lg font-semibold mb-2">Signed in</h1>
          <p className="text-sm text-muted mb-4">{auth.user.email}</p>
          <button className="btn-ghost" onClick={() => auth.signOut()}>
            Sign out
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="card max-w-md w-full">
        <h1 className="text-lg font-semibold mb-4">Sign in</h1>
        <div className="flex gap-2 mb-4 text-sm">
          <button
            className={mode === "password" ? "btn" : "btn-ghost"}
            onClick={() => setMode("password")}
            type="button"
          >
            Password
          </button>
          <button
            className={mode === "magic" ? "btn" : "btn-ghost"}
            onClick={() => setMode("magic")}
            type="button"
          >
            Magic link
          </button>
        </div>
        <form onSubmit={submit} className="flex flex-col gap-3">
          <input
            className="input"
            placeholder="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          {mode === "password" && (
            <input
              className="input"
              placeholder="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          )}
          <div className="flex gap-2">
            <button className="btn" disabled={busy} type="submit">
              {busy ? "Working…" : mode === "magic" ? "Send link" : "Sign in"}
            </button>
            {mode === "password" && (
              <button
                className="btn-ghost"
                disabled={busy}
                type="button"
                onClick={signup}
              >
                Create account
              </button>
            )}
          </div>
          {msg && <p className="text-sm text-ok">{msg}</p>}
          {err && <p className="text-sm text-bad">{err}</p>}
        </form>
      </div>
    </div>
  );
}