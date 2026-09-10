"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { Session, User as SupabaseUser } from "@supabase/supabase-js";
import { getSupabase } from "@/lib/supabase";
import { api, getToken, setToken } from "@/lib/api";

export type AuthUser = {
  id: string;
  email: string;
  name: string;
  roles: string[];
};

export type AuthStatus = "loading" | "authed" | "anon";

type AuthContextType = {
  status: AuthStatus;
  user: AuthUser | null;
  supabaseUser: SupabaseUser | null;
  session: Session | null;
  token: string | null;
  isAuthModalOpen: boolean;
  authModalMode: "signin" | "signup";
  openAuthModal: (mode?: "signin" | "signup") => void;
  closeAuthModal: () => void;
  signInWithPassword: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, name?: string) => Promise<void>;
  signInWithOtp: (email: string) => Promise<void>;
  signOut: () => Promise<void>;
  refreshSession: () => Promise<void>;
  // For backwards compatibility with existing pages
  getAccessToken: () => Promise<string | null>;
};

const AuthContext = createContext<AuthContextType | null>(null);

export function SupabaseAuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [supabaseUser, setSupabaseUser] = useState<SupabaseUser | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [token, setTokenState] = useState<string | null>(null);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [authModalMode, setAuthModalMode] = useState<"signin" | "signup">("signin");

  const client = useMemo(() => getSupabase(), []);

  const openAuthModal = useCallback((mode: "signin" | "signup" = "signin") => {
    setAuthModalMode(mode);
    setIsAuthModalOpen(true);
  }, []);

  const closeAuthModal = useCallback(() => {
    setIsAuthModalOpen(false);
  }, []);

  // Hydrate user profile from backend
  const hydrateUser = useCallback(async () => {
    try {
      const me = await api.me();
      setUser(me);
      setStatus("authed");
      return me;
    } catch {
      // If api.me() fails (e.g. invalid token), clear state
      setToken(null);
      setTokenState(null);
      setUser(null);
      setStatus("anon");
      return null;
    }
  }, []);

  const refreshSession = useCallback(async () => {
    if (client) {
      const { data } = await client.auth.getSession();
      if (data.session) {
        setSession(data.session);
        setSupabaseUser(data.session.user);
        setTokenState(data.session.access_token);
        // Supabase JWT is accepted directly by MAICOS backend
        try {
          const me = await api.me();
          setUser(me);
          setStatus("authed");
          return;
        } catch {
          // Fall back to using session email as basic user
          if (data.session.user?.email) {
            setUser({
              id: data.session.user.id,
              email: data.session.user.email,
              name: data.session.user.user_metadata?.name || data.session.user.email.split("@")[0],
              roles: ["admin", "owner"],
            });
            setStatus("authed");
            return;
          }
        }
      }
    }

    // Check native localStorage token
    const local = getToken();
    if (local) {
      setTokenState(local);
      await hydrateUser();
      return;
    }

    // Neither exists
    setUser(null);
    setSupabaseUser(null);
    setSession(null);
    setTokenState(null);
    setStatus("anon");
  }, [client, hydrateUser]);

  useEffect(() => {
    refreshSession();

    if (!client) return;

    const { data: sub } = client.auth.onAuthStateChange(async (_event, newSession) => {
      if (newSession) {
        setSession(newSession);
        setSupabaseUser(newSession.user);
        setTokenState(newSession.access_token);
        try {
          const me = await api.me();
          setUser(me);
          setStatus("authed");
        } catch {
          if (newSession.user?.email) {
            setUser({
              id: newSession.user.id,
              email: newSession.user.email,
              name: newSession.user.user_metadata?.name || newSession.user.email.split("@")[0],
              roles: ["admin", "owner"],
            });
            setStatus("authed");
          }
        }
      } else {
        const local = getToken();
        if (!local) {
          setSession(null);
          setSupabaseUser(null);
          setUser(null);
          setStatus("anon");
        }
      }
    });

    return () => {
      sub.subscription.unsubscribe();
    };
  }, [client, refreshSession]);

  const signInWithPassword = useCallback(
    async (email: string, password: string) => {
      const cleanEmail = email.trim().toLowerCase();
      if (!cleanEmail || !cleanEmail.includes("@")) {
        throw new Error("Please enter a valid email address");
      }
      if (!password) {
        throw new Error("Please enter your password");
      }

      let authed = false;

      // 1. Try Supabase Auth if configured
      if (client) {
        try {
          const { data, error } = await client.auth.signInWithPassword({
            email: cleanEmail,
            password,
          });
          if (!error && data.session) {
            setSession(data.session);
            setSupabaseUser(data.user);
            setTokenState(data.session.access_token);
            authed = true;
          }
        } catch {
          // Continue to native fallback
        }
      }

      // 2. Fallback to MAICOS native auth
      if (!authed) {
        try {
          const res = await api.login(cleanEmail, password);
          if (res.access_token) {
            setToken(res.access_token);
            setTokenState(res.access_token);
            authed = true;
          }
        } catch (err) {
          throw new Error((err as Error).message || "Invalid email or password");
        }
      }

      if (authed) {
        await refreshSession();
        setIsAuthModalOpen(false);
      }
    },
    [client, refreshSession]
  );

  const signUp = useCallback(
    async (email: string, password: string, name?: string) => {
      const cleanEmail = email.trim().toLowerCase();
      if (!cleanEmail || !cleanEmail.includes("@")) {
        throw new Error("Please enter a valid email address");
      }
      if (!password || password.length < 6) {
        throw new Error("Password must be at least 6 characters");
      }

      // 1. Try Supabase signup if configured
      if (client) {
        try {
          await client.auth.signUp({
            email: cleanEmail,
            password,
            options: { data: { name: name || cleanEmail.split("@")[0] } },
          });
        } catch {
          // non-fatal, try native register
        }
      }

      // 2. Register natively in MAICOS database to guarantee instant JWT & workspace
      try {
        const res = await api.register(cleanEmail, password, name);
        if (res.access_token) {
          setToken(res.access_token);
          setTokenState(res.access_token);
          await refreshSession();
          setIsAuthModalOpen(false);
          return;
        }
      } catch (e) {
        const msg = (e as Error).message;
        if (msg.includes("already registered")) {
          await signInWithPassword(cleanEmail, password);
          return;
        }
        throw new Error(msg);
      }
    },
    [client, refreshSession, signInWithPassword]
  );

  const signInWithOtp = useCallback(
    async (email: string) => {
      if (!client) throw new Error("Magic links require Supabase to be configured");
      const cleanEmail = email.trim().toLowerCase();
      const { error } = await client.auth.signInWithOtp({
        email: cleanEmail,
        options: {
          emailRedirectTo:
            typeof window !== "undefined" ? window.location.origin : undefined,
        },
      });
      if (error) throw error;
    },
    [client]
  );

  const signOut = useCallback(async () => {
    if (client) {
      try {
        await client.auth.signOut();
      } catch {
        // ignore
      }
    }
    setToken(null);
    setTokenState(null);
    setSession(null);
    setSupabaseUser(null);
    setUser(null);
    setStatus("anon");
  }, [client]);

  const getAccessToken = useCallback(async () => {
    if (client) {
      const { data } = await client.auth.getSession();
      if (data.session?.access_token) return data.session.access_token;
    }
    return getToken();
  }, [client]);

  const value = useMemo<AuthContextType>(
    () => ({
      status,
      user,
      supabaseUser,
      session,
      token,
      isAuthModalOpen,
      authModalMode,
      openAuthModal,
      closeAuthModal,
      signInWithPassword,
      signUp,
      signInWithOtp,
      signOut,
      refreshSession,
      getAccessToken,
    }),
    [
      status,
      user,
      supabaseUser,
      session,
      token,
      isAuthModalOpen,
      authModalMode,
      openAuthModal,
      closeAuthModal,
      signInWithPassword,
      signUp,
      signInWithOtp,
      signOut,
      refreshSession,
      getAccessToken,
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <SupabaseAuthProvider>");
  return ctx;
}

// Backward compatibility alias
export function useSupabaseAuth() {
  return useAuth();
}