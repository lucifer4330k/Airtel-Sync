"use client";

import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
type State = "checking" | "live" | "waking" | "offline";

/** Free hosts sleep when idle; the first request wakes the API (~1 min). */
export function ApiStatus({ className }: { className?: string }) {
  const [state, setState] = useState<State>("checking");

  useEffect(() => {
    let cancelled = false;
    async function ping(attempt: number) {
      try {
        const ctrl = new AbortController();
        const timer = setTimeout(() => ctrl.abort(), 8000);
        const r = await fetch(`${API_URL}/health`, { signal: ctrl.signal });
        clearTimeout(timer);
        const body = await r.json();
        if (!cancelled) setState(body.database === "ok" ? "live" : "waking");
        if (body.database !== "ok" && attempt < 12 && !cancelled) setTimeout(() => ping(attempt + 1), 10000);
      } catch {
        if (cancelled) return;
        setState(attempt < 12 ? "waking" : "offline");
        if (attempt < 12) setTimeout(() => ping(attempt + 1), 10000);
      }
    }
    void ping(0);
    return () => {
      cancelled = true;
    };
  }, []);

  const label = {
    checking: "Checking the API…",
    live: "API live",
    waking: "API waking up (free hosting sleeps when idle, about a minute)",
    offline: "API unreachable",
  }[state];

  return (
    <p role="status" className={cn("flex items-center gap-2 text-sm text-ink-soft", className)}>
      <span
        aria-hidden
        className={cn(
          "size-2 rounded-full",
          state === "live" && "bg-stamp",
          (state === "waking" || state === "checking") && "animate-pulse bg-marigold",
          state === "offline" && "bg-alert",
        )}
      />
      {label}
    </p>
  );
}
