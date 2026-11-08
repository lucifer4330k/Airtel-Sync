"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { consoleApi, consoleSession, type ConsoleOrder, type OutboxItem } from "@/lib/console";

export default function OrdersPage() {
  const [orders, setOrders] = useState<ConsoleOrder[] | null>(null);
  const [outbox, setOutbox] = useState<OutboxItem[]>([]);
  const [reason, setReason] = useState<Record<number, string>>({});
  const [error, setError] = useState<string | null>(null);
  const isAdmin = consoleSession.get()?.user.role === "admin";

  const load = useCallback(() => {
    consoleApi.orders().then(setOrders).catch((e) => setError(String(e.message ?? e)));
    consoleApi.outbox().then(setOutbox).catch(() => undefined);
  }, []);
  useEffect(load, [load]);

  async function act(fn: () => Promise<unknown>) {
    setError(null);
    try {
      await fn();
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  return (
    <div className="grid max-w-6xl gap-6 xl:grid-cols-[1fr_24rem]">
      <section>
        <h1 className="text-2xl font-semibold">Orders</h1>
        <p className="text-sm text-ink-soft">
          {isAdmin ? "Advance an order to simulate install progress in the demo. Each step messages the owner." : "Read-only for your role."}
        </p>
        {error && <p role="alert" className="mt-3 text-sm text-alert">{error}</p>}
        {orders === null ? (
          <p className="mt-4 animate-pulse text-ink-soft">Loading…</p>
        ) : orders.length === 0 ? (
          <p className="mt-4 rounded-bill border border-line bg-surface p-4 text-ink-soft">No orders yet.</p>
        ) : (
          <ul className="mt-4 flex flex-col gap-3">
            {orders.map((o) => (
              <li key={o.id} className="rounded-bill border border-line bg-surface p-4">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="font-medium">
                    #{o.id} {o.business} <span className="font-normal text-ink-soft">· {o.city}</span>
                  </p>
                  <p className="text-sm font-semibold text-pen">{o.state_label}</p>
                </div>
                {o.hold_reason && <p className="mt-1 text-sm text-marigold">On hold: {o.hold_reason}</p>}
                <p className="mt-1 text-sm text-ink-soft">
                  ETA {o.eta_date ? new Date(o.eta_date).toLocaleDateString("en-IN") : "–"}
                  {o.engineer_slot && ` · visit ${new Date(o.engineer_slot).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}`}
                </p>
                {isAdmin && o.state !== "activated" && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button className="min-h-10 text-sm" onClick={() => act(() => consoleApi.advance(o.id))}>
                      {o.state === "on_hold" ? "Resume" : "Advance to next step"}
                    </Button>
                    {o.state !== "on_hold" && (
                      <>
                        <label htmlFor={`hold-${o.id}`} className="sr-only">
                          Hold reason
                        </label>
                        <input
                          id={`hold-${o.id}`}
                          value={reason[o.id] ?? ""}
                          onChange={(e) => setReason((r) => ({ ...r, [o.id]: e.target.value }))}
                          placeholder="Hold reason"
                          className="min-h-10 min-w-0 flex-1 rounded-bill border border-line bg-paper px-3 text-sm"
                        />
                        <Button
                          variant="quiet"
                          className="min-h-10 text-sm"
                          disabled={(reason[o.id] ?? "").trim().length < 3}
                          onClick={() => act(() => consoleApi.hold(o.id, reason[o.id]))}
                        >
                          Put on hold
                        </Button>
                      </>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2 className="font-semibold">WhatsApp outbox</h2>
        <p className="text-sm text-ink-soft">What owners received. “mocked” means no WhatsApp sandbox is configured.</p>
        <ol className="mt-3 flex flex-col gap-2">
          {outbox.map((n) => (
            <li key={n.id} className="rounded-bill border border-line bg-surface p-3 text-sm">
              <p className="text-xs text-ink-soft">
                {n.to ?? "no number"} · {n.status} · {new Date(n.at).toLocaleTimeString("en-IN", { timeStyle: "short" })}
              </p>
              <p className="mt-1 whitespace-pre-line break-words">{n.body}</p>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
