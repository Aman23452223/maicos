"use client";

import { useEffect, useState } from "react";
import { getSupabase, isSupabaseEnabled } from "./supabase";
import type { RealtimeChannel } from "@supabase/supabase-js";

type Payload<T> = {
  new?: T;
  old?: T;
  eventType: "INSERT" | "UPDATE" | "DELETE" | string;
};

/** Subscribe to a Supabase Realtime channel.

Returns a `data` array of the channel's row payloads. The channel is
unsubscribed on unmount. When Supabase is disabled, returns an empty
array (so call sites can render without guarding).

Usage:

    const { data } = useRealtime<Workflow>("workflows");
    data.forEach((w) => console.log(w));
*/
export function useRealtime<T = Record<string, unknown>>(
  table: string,
  filter?: string,
): { data: T[]; status: "disabled" | "loading" | "ready" | "error" } {
  const [data, setData] = useState<T[]>([]);
  const [status, setStatus] = useState<
    "disabled" | "loading" | "ready" | "error"
  >(() => (isSupabaseEnabled() ? "loading" : "disabled"));

  useEffect(() => {
    if (!isSupabaseEnabled()) return;
    const client = getSupabase();
    if (!client) {
      setStatus("disabled");
      return;
    }
    // The supabase-js 2.45 typings for `channel().on()` are strict
    // around template literals; cast to any at the boundary.
    const ch = client.channel(`public:${table}`) as unknown as {
      on: (
        type: string,
        filter: Record<string, unknown>,
        cb: (payload: Payload<T>) => void,
      ) => RealtimeChannel;
      subscribe: (cb?: (status: string) => void) => RealtimeChannel;
    };
    const channel = ch.on(
      "postgres_changes",
      {
        event: "*",
        schema: "public",
        table,
        ...(filter ? { filter } : {}),
      },
      (payload) => {
        setData((current) => {
          if (payload.eventType === "DELETE" && payload.old) {
            return current.filter(
              (row) => (row as { id?: string }).id !== (payload.old as { id?: string }).id,
            );
          }
          const next = (payload.new ?? payload.old) as T;
          const id = (next as { id?: string }).id;
          if (!id) return [next, ...current];
          const idx = current.findIndex((r) => (r as { id?: string }).id === id);
          if (idx === -1) return [next, ...current];
          const copy = current.slice();
          copy[idx] = next;
          return copy;
        });
      },
    );
    channel.subscribe((status: string) => {
      if (status === "SUBSCRIBED") setStatus("ready");
      else if (status === "CHANNEL_ERROR" || status === "TIMED_OUT")
        setStatus("error");
    });

    return () => {
      client.removeChannel(channel);
    };
  }, [table, filter]);

  return { data, status };
}