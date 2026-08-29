"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, setToken } from "@/lib/api";
import { useSupabaseAuth } from "@/contexts/AuthContext";

export function Topbar() {
  const supa = useSupabaseAuth();
  const [email, setEmail] = useState<string | null>(null);
  const [pw, setPw] = useState("");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined" && localStorage.getItem("maicos.token")) {
      api
        .me()
        .then((u) => setEmail(u.email))
        .catch(() => setToken(null));
    }
  }, []);

  async function login() {
    setErr(null);
    try {
      const { access_token } = await api.login(email ?? "", pw);
      setToken(access_token);
      window.location.reload();
    } catch (e) {
      setErr((e as Error).message);
    }
  }

  function logout() {
    setToken(null);
    setEmail(null);
    window.location.reload();
  }

  const supaUser =
    supa.status === "authed" ? supa.user.email ?? supa.user.id : null;

  return (
    <header className="border-b border-line p-3 flex items-center gap-2">
      <div className="flex items-center gap-2 flex-1">
        {!email && (
          <>
            <input
              className="input max-w-xs"
              placeholder="email"
              onChange={(e) => setEmail(e.target.value)}
            />
            <input
              className="input max-w-xs"
              placeholder="password"
              type="password"
              onChange={(e) => setPw(e.target.value)}
            />
            <button className="btn" onClick={login}>
              Sign in
            </button>
            {err && <span className="text-bad text-sm ml-2">{err}</span>}
          </>
        )}
        {email && (
          <div className="text-sm text-muted">
            Signed in as {email}
          </div>
        )}
      </div>
      <div className="flex items-center gap-3">
        {supaUser && (
          <div className="text-xs text-muted">
            Supabase: <span className="text-fg">{supaUser}</span>
          </div>
        )}
        {supa.status === "anon" && (
          <Link href="/login" className="btn-ghost text-sm">
            Supabase sign-in
          </Link>
        )}
        {email && (
          <button className="btn-ghost" onClick={logout}>
            Sign out
          </button>
        )}
        {supa.status === "authed" && (
          <button className="btn-ghost" onClick={() => supa.signOut()}>
            Supabase sign-out
          </button>
        )}
      </div>
    </header>
  );
}
