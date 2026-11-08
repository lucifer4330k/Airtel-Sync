"use client";

import { SlidersHorizontal, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { RepairOptions } from "@/components/repair-options";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import type { OwnerSession, Quote } from "@/lib/journey";
import { PRIMARY_CONNECTIONS, repairApi, type RepairOption, type RepairResult, type WhatIf } from "@/lib/repair";

/**
 * "What if my budget or needs change?" The owner changes a constraint; the
 * server explains what breaks and offers the smallest valid fix, or a clear
 * trade-off, or a specialist handoff that keeps the need. Nothing changes
 * until the owner picks an option.
 */
export function WhatIfPanel({
  quote,
  session,
  onApplied,
}: {
  quote: Quote;
  session: OwnerSession;
  onApplied: (q: Quote | null, message?: string) => void;
}) {
  const t = useTranslations("whatif");
  const [open, setOpen] = useState(false);
  const [budget, setBudget] = useState("");
  const [sites, setSites] = useState("");
  const [tier, setTier] = useState<"" | "1" | "2">("");
  const [noGst, setNoGst] = useState(false);
  const [connection, setConnection] = useState("");
  const [add, setAdd] = useState<string[]>([]);
  const [essential, setEssential] = useState<string[]>([]);
  const [result, setResult] = useState<RepairResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const currentPrimary = quote.items.find((i) => PRIMARY_CONNECTIONS.some((c) => c.id === i.product_id))?.product_id;
  const addable = quote.addons.filter((a) => !a.included);
  const essentialsPool = [
    ...quote.items.map((i) => ({ id: i.product_id, name: i.name })),
    ...addable.filter((a) => add.includes(a.product_id)).map((a) => ({ id: a.product_id, name: a.name })),
  ];

  function body(): WhatIf {
    return {
      budget: budget ? Number(budget) : null,
      sites: sites ? Number(sites) : null,
      city_tier: tier ? (Number(tier) as 1 | 2) : null,
      gstin_active: noGst ? false : null,
      connection: connection || null,
      add,
      must_have: essential,
    };
  }

  async function check() {
    setBusy(true);
    setError(null);
    try {
      setResult(await repairApi.whatIf(quote.id, session, body()));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function choose(o: RepairOption) {
    setBusy(true);
    setError(null);
    try {
      const r = await repairApi.apply(quote.id, session, { ...body(), option_id: o.id });
      if ("handoff" in r) onApplied(null, r.message);
      else onApplied(r);
      setOpen(false);
      setResult(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  const toggle = (list: string[], set: (v: string[]) => void, id: string) =>
    set(list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);

  if (!open) {
    return (
      <Button variant="quiet" width="full" onClick={() => setOpen(true)} className="print:hidden">
        <SlidersHorizontal aria-hidden className="size-4" />
        {t("open")}
      </Button>
    );
  }

  return (
    <section aria-label={t("title")} className="rounded-bill border border-pen/40 bg-surface p-4 print:hidden">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="font-semibold">{t("title")}</h2>
          <p className="text-sm text-ink-soft">{t("help")}</p>
        </div>
        <button
          type="button"
          onClick={() => setOpen(false)}
          aria-label={t("close")}
          className="flex size-11 shrink-0 cursor-pointer items-center justify-center rounded-bill hover:bg-paper"
        >
          <X aria-hidden className="size-4" />
        </button>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <label className="col-span-2 flex flex-col gap-1">
          {t("budget")}
          <input
            inputMode="numeric"
            value={budget}
            onChange={(e) => setBudget(e.target.value.replace(/\D/g, ""))}
            placeholder={`${quote.monthly_total}`}
            className="money min-h-11 rounded-bill border border-line bg-paper px-3"
          />
        </label>
        <label className="flex flex-col gap-1">
          {t("sites")}
          <input
            inputMode="numeric"
            value={sites}
            onChange={(e) => setSites(e.target.value.replace(/\D/g, ""))}
            className="money min-h-11 rounded-bill border border-line bg-paper px-3"
          />
        </label>
        <label className="flex flex-col gap-1">
          {t("city")}
          <select value={tier} onChange={(e) => setTier(e.target.value as "" | "1" | "2")} className="min-h-11 cursor-pointer rounded-bill border border-line bg-paper px-2">
            <option value="">{t("keep")}</option>
            <option value="1">{t("metro")}</option>
            <option value="2">{t("smaller")}</option>
          </select>
        </label>
        <label className="col-span-2 flex flex-col gap-1">
          {t("connection")}
          <select value={connection} onChange={(e) => setConnection(e.target.value)} className="min-h-11 cursor-pointer rounded-bill border border-line bg-paper px-2">
            <option value="">{t("keep")}</option>
            {PRIMARY_CONNECTIONS.filter((c) => c.id !== currentPrimary).map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label className="col-span-2 flex min-h-11 cursor-pointer items-center gap-3">
          <input type="checkbox" checked={noGst} onChange={(e) => setNoGst(e.target.checked)} className="size-5 accent-[rgb(var(--pen))]" />
          {t("no_gst")}
        </label>
      </div>

      {addable.length > 0 && (
        <fieldset className="mt-4">
          <legend className="text-sm font-medium">{t("add")}</legend>
          <div className="mt-2 flex flex-wrap gap-2">
            {addable.map((a) => (
              <button
                key={a.product_id}
                type="button"
                aria-pressed={add.includes(a.product_id)}
                onClick={() => toggle(add, setAdd, a.product_id)}
                className="min-h-10 cursor-pointer rounded-bill border border-line px-3 text-sm aria-pressed:border-pen aria-pressed:bg-pen aria-pressed:text-white"
              >
                {a.name}
              </button>
            ))}
          </div>
        </fieldset>
      )}

      <fieldset className="mt-4">
        <legend className="text-sm font-medium">{t("essential")}</legend>
        <div className="mt-2 flex flex-col gap-1">
          {essentialsPool.map((p) => (
            <label key={p.id} className="flex min-h-10 cursor-pointer items-center gap-3 text-sm">
              <input
                type="checkbox"
                checked={essential.includes(p.id)}
                onChange={() => toggle(essential, setEssential, p.id)}
                className="size-5 accent-[rgb(var(--pen))]"
              />
              {p.name}
            </label>
          ))}
        </div>
      </fieldset>

      <Button width="full" className="mt-4" disabled={busy} onClick={check}>
        {busy && !result ? t("checking") : t("check")}
      </Button>
      {error && (
        <p role="alert" className="mt-3 text-sm text-alert">
          {error}
        </p>
      )}

      {result && (
        <div className="mt-5">
          <RepairOptions
            result={result}
            currentTotal={quote.monthly_total}
            budget={budget ? Number(budget) : null}
            onChoose={choose}
            busy={busy}
            chooseLabel={t("use")}
          />
          {result.needs_choice && <p className="mt-3 text-sm text-ink-soft">{t("choose")}</p>}
        </div>
      )}
    </section>
  );
}
