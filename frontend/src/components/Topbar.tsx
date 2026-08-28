"use client";

import { useEffect, useState } from "react";
import { api, setToken } from "@/lib/api";

export function Topbar() {
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
  }

  if (!email) {
    return (
      <header className="border-b border-line p-3 flex items-center gap-2">
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
      </header>
    );
  }
  return (
    <header className="border-b border-line p-3 flex items-center justify-between">
      <div className="text-sm text-muted">Signed in as {email}</div>
      <button className="btn-ghost" onClick={logout}>
        Sign out
      </button>
    </header>
  );
}
