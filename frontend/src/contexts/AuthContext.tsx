"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { Session, User } from "@supabase/supabase-js";
import { getSupabase, isSupabaseEnabled } from "@/lib/supabase";

type AuthState =
  | { status: "loading" }
  | { status: "disabled" }
  | { status: "anon" }
  | { status: "authed"; session: Session; user: User };

type AuthApi = {
  signInWithPassword: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<void>;
  signInWithOtp: (email: string) => Promise<void>;
  signOut: () => Promise<void>;
  getAccessToken: () => Promise<string | null>;
};

const AuthContext = createContext<(AuthState & AuthApi) | null>(null);

export function SupabaseAuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(() =>
    isSupabaseEnabled() ? { status: "loading" } : { status: "disabled" },
  );

  const client = useMemo(() => getSupabase(), []);

  useEffect(() => {
    if (!client) {
      setState({ status: "disabled" });
      return;
    }
    let mounted = true;
    client.auth.getSession().then(({ data }: { data: { session: Session | null } }) => {
      if (!mounted) return;
      if (data.session) setState({ status: "authed", session: data.session, user: data.session.user });
      else setState({ status: "anon" });
    });
    const { data: sub } = client.auth.onAuthStateChange((_event: string, session: Session | null) => {
      if (!mounted) return;
      if (session) setState({ status: "authed", session, user: session.user });
      else setState({ status: "anon" });
    });
    return () => {
      mounted = false;
      sub.subscription.unsubscribe();
    };
  }, [client]);

  const api: AuthApi = useMemo(
    () => ({
      async signInWithPassword(email, password) {
        if (!client) throw new Error("Supabase not configured");
        const { error } = await client.auth.signInWithPassword({ email, password });
        if (error) throw error;
      },
      async signUp(email, password) {
        if (!client) throw new Error("Supabase not configured");
        const { error } = await client.auth.signUp({ email, password });
        if (error) throw error;
      },
      async signInWithOtp(email) {
        if (!client) throw new Error("Supabase not configured");
        const { error } = await client.auth.signInWithOtp({ email, options: { emailRedirectTo: typeof window !== "undefined" ? window.location.origin : undefined } });
        if (error) throw error;
      },
      async signOut() {
        if (!client) return;
        const { error } = await client.auth.signOut();
        if (error) throw error;
      },
      async getAccessToken() {
        if (!client) return null;
        const { data } = await client.auth.getSession();
        return data.session?.access_token ?? null;
      },
    }),
    [client],
  );

  return <AuthContext.Provider value={{ ...state, ...api }}>{children}</AuthContext.Provider>;
}

export function useSupabaseAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useSupabaseAuth must be used inside <SupabaseAuthProvider>");
  return ctx;
}