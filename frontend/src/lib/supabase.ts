"use client";

import { createClient, SupabaseClient } from "@supabase/supabase-js";

let cached: SupabaseClient | null = null;

export function isSupabaseEnabled(): boolean {
  const flag = process.env.NEXT_PUBLIC_SUPABASE_ENABLED;
  if (flag === "true" || flag === "1") return true;
  return Boolean(getSupabaseConfig().url && getSupabaseConfig().anonKey);
}

export function getSupabaseConfig(): { url: string | null; anonKey: string | null } {
  const url =
    process.env.NEXT_PUBLIC_SUPABASE_URL?.trim() || null;
  const anonKey =
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY?.trim() ||
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY?.trim() ||
    null;
  return { url, anonKey };
}

export function getSupabase(): SupabaseClient | null {
  if (!isSupabaseEnabled()) return null;
  if (cached) return cached;
  const { url, anonKey } = getSupabaseConfig();
  if (!url || !anonKey) return null;
  cached = createClient(url, anonKey, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,
      storageKey: "maicos.supabase.auth",
    },
  });
  return cached;
}