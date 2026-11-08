"use client";

import { Printer, Share2 } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";

import { AddonList } from "@/components/addon-list";
import { Bill } from "@/components/bill";
import { WhatIfPanel } from "@/components/what-if";
import { Button, ButtonLink } from "@/components/ui/button";
import { ApiError, type PricedBundle, type Segment } from "@/lib/api";
import { owner, plan, quotes as quoteApi, type Quote } from "@/lib/journey";
import { cn } from "@/lib/utils";

function QuoteView() {
  const t = useTranslations("quote");
  const locale = useLocale();
  const router = useRouter();
  const params = useSearchParams();
  const qParam = Number(params.get("q")) || null;
  const share = params.get("share");

  const [all, setAll] = useState<Quote[] | null>(null);
  const [selected, setSelected] = useState<number | null>(qParam);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [gstNote, setGstNote] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      // 1. Shared read-only link
      if (qParam && share) {
        setAll([await quoteApi.get(qParam, null, share)]);
        setSelected(qParam);
        return;
      }
      // 2. Profile in the URL ("I know what I need"): build a plan first
      const segment = params.get("segment") as Segment | null;
      if (!qParam && segment) {
        const res = await quoteApi.create(
          {
            segment,
            city_tier: Number(params.get("city_tier")) === 1 ? 1 : 2,
            employees: Number(params.get("employees") || 1),
            sites: Number(params.get("sites") || 1),
            gstin: params.get("gstin"),
          },
          locale,
        );
        owner.set({ businessId: res.business_id, token: res.owner_token });
        plan.set({ quoteIds: res.quotes.map((q) => q.id), recommended: res.recommended });
        setGstNote(!res.gstin_active);
        router.replace(`/quote?q=${res.recommended}`);
        return;
      }
      // 3. Owner's own plan
      const s = owner.get();
      const p = plan.get();
      if (!s || !p) {
        setAll([]);
        return;
      }
      const loaded = await Promise.all(p.quoteIds.map((id) => quoteApi.get(id, s)));
      setAll(loaded);
      setSelected((cur) => cur ?? p.recommended);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("error"));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qParam, share]);

  useEffect(() => {
    void load();
  }, [load]);

  async function toggle(productId: string, include: boolean): Promise<string | null> {
    const s = owner.get();
    if (!s || !selected) return null;
    try {
      const updated = await quoteApi.toggle(selected, s, productId, include);
      setAll((qs) => qs?.map((q) => (q.id === updated.id ? updated : q)) ?? null);
      return null;
    } catch (e) {
      return e instanceof ApiError ? e.message : t("error");
    }
  }

  async function copyShare(q: Quote) {
    const url = `${window.location.origin}/quote?q=${q.id}&share=${encodeURIComponent(q.share_token)}`;
    try {
      if (navigator.share) await navigator.share({ title: t("title"), url });
      else await navigator.clipboard.writeText(url);
      setCopied(true);
    } catch {
      /* dismissed */
    }
  }

  if (error) {
    return (
      <div role="alert" className="flex flex-col gap-4 rounded-bill border border-alert/40 bg-surface p-4">
        <p>{error}</p>
        <Button variant="quiet" onClick={load}>
          {t("retry")}
        </Button>
      </div>
    );
  }
  if (all === null) {
    return (
      <p aria-busy className="animate-pulse text-ink-soft">
        {t("loading")}
      </p>
    );
  }
  if (all.length === 0) {
    return (
      <div className="flex flex-col gap-4 pt-4">
        <p>{t("no_profile")}</p>
        <ButtonLink href="/chat">{t("to_advisor")}</ButtonLink>
      </div>
    );
  }

  const quote = all.find((q) => q.id === selected) ?? all[0];
  const readOnly = Boolean(share) || quote.status !== "draft";

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-start justify-between gap-3">
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
        <div className="flex gap-1 print:hidden">
          {!share && (
            <Button variant="link" className="px-2 text-sm" onClick={() => copyShare(quote)}>
              <Share2 aria-hidden className="size-4" />
              {copied ? t("copied") : t("share")}
            </Button>
          )}
          <Button variant="link" className="px-2 text-sm" onClick={() => window.print()}>
            <Printer aria-hidden className="size-4" />
            {t("pdf")}
          </Button>
        </div>
      </div>

      {all.length > 1 && (
        <div role="radiogroup" aria-label={t("title")} className="grid grid-flow-col gap-1 rounded-bill bg-line/60 p-1 print:hidden">
          {all.map((q) => (
            <button
              key={q.id}
              role="radio"
              aria-checked={q.id === quote.id}
              onClick={() => setSelected(q.id)}
              className={cn(
                "relative min-h-11 cursor-pointer rounded-[4px] px-2 text-sm font-medium transition-colors",
                q.id === quote.id ? "bg-surface text-ink shadow-sm" : "text-ink-soft hover:text-ink",
              )}
            >
              {t(q.tier)}
              {q.id === plan.get()?.recommended && (
                <span aria-hidden className="absolute right-1.5 top-1.5 size-2 rounded-full bg-marigold" />
              )}
            </button>
          ))}
        </div>
      )}

      <Bill bundle={quote as unknown as PricedBundle} />

      {gstNote && <p className="text-sm text-ink-soft">{t("gst_note")}</p>}

      {!readOnly && quote.addons.length > 0 && (
        <section className="flex flex-col gap-2 print:hidden">
          <h2 className="font-semibold">{t("addons_title")}</h2>
          <AddonList options={quote.addons} onToggle={toggle} />
        </section>
      )}

      {!readOnly && owner.get() && (
        <WhatIfPanel
          key={quote.id}
          quote={quote}
          session={owner.get()!}
          onApplied={(updated, message) => {
            if (updated) setAll((qs) => qs?.map((q) => (q.id === updated.id ? updated : q)) ?? null);
            setNotice(message ?? t("updated"));
          }}
        />
      )}
      {notice && (
        <p role="status" className="rounded-bill border border-stamp/40 bg-surface p-3 text-sm">
          {notice}
        </p>
      )}

      {!readOnly && (
        <ButtonLink href={`/checkout?q=${quote.id}`} width="full" className="print:hidden">
          {t("accept")}
        </ButtonLink>
      )}
      {quote.status !== "draft" && !share && <p className="text-sm text-ink-soft">{t(`status_${quote.status}`)}</p>}
    </div>
  );
}

export default function QuotePage() {
  return (
    <Suspense>
      <QuoteView />
    </Suspense>
  );
}
