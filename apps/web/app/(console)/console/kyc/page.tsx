"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { consoleApi, type QueueItem } from "@/lib/console";

const DOC = {
  gst_certificate: "GST certificate",
  udyam_certificate: "Udyam certificate",
  signatory_id: "Signatory ID",
  address_proof: "Address proof",
} as Record<string, string>;

export default function KycQueue() {
  const [items, setItems] = useState<QueueItem[] | null>(null);
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [done, setDone] = useState<Record<number, string>>({});
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    consoleApi.queue().then(setItems).catch((e) => setError(String(e.message ?? e)));
  }, []);
  useEffect(load, [load]);

  async function resolve(item: QueueItem, result: "pass" | "fail") {
    setError(null);
    try {
      const r = await consoleApi.resolve(item.check_id, result, notes[item.check_id] ?? "");
      setDone((d) => ({ ...d, [item.check_id]: `${result === "pass" ? "Approved" : "Rejected"}. Case is now ${r.overall}.` }));
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <header>
        <h1 className="text-2xl font-semibold">KYC review</h1>
        <p className="text-sm text-ink-soft">
          Checks the system could not decide alone. The owner is never blocked while these wait. Every decision is logged.
        </p>
      </header>
      {error && <p role="alert" className="text-sm text-alert">{error}</p>}
      {Object.entries(done).map(([id, msg]) => (
        <p key={id} role="status" className="rounded-bill border border-stamp/40 bg-surface p-2 text-sm">
          {msg}
        </p>
      ))}
      {items === null ? (
        <p className="animate-pulse text-ink-soft">Loading…</p>
      ) : items.length === 0 ? (
        <p className="rounded-bill border border-line bg-surface p-4 text-ink-soft">Nothing waiting for review.</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {items.map((item) => (
            <li key={item.check_id} className="rounded-bill border border-line bg-surface p-4">
              <p className="font-medium">
                {item.business} <span className="font-normal text-ink-soft">· {DOC[item.doc_type] ?? item.doc_type} · {item.city ?? ""}</span>
              </p>
              <p className="mt-1 text-sm">{item.reason}</p>
              <label htmlFor={`note-${item.check_id}`} className="mt-3 block text-xs text-ink-soft">
                Note (required)
              </label>
              <input
                id={`note-${item.check_id}`}
                value={notes[item.check_id] ?? ""}
                onChange={(e) => setNotes((n) => ({ ...n, [item.check_id]: e.target.value }))}
                placeholder="e.g. Board resolution authorises the signatory"
                className="mt-1 min-h-10 w-full rounded-bill border border-line bg-paper px-3 text-sm"
              />
              <div className="mt-2 flex gap-2">
                <Button className="min-h-10 text-sm" disabled={(notes[item.check_id] ?? "").trim().length < 2} onClick={() => resolve(item, "pass")}>
                  Approve
                </Button>
                <Button variant="quiet" className="min-h-10 text-sm" disabled={(notes[item.check_id] ?? "").trim().length < 2} onClick={() => resolve(item, "fail")}>
                  Reject
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
