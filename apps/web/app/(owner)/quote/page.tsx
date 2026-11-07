"use client";

import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";

import { Bill } from "@/components/bill";
import { Button, ButtonLink } from "@/components/ui/button";
import { api, type Profile, type QuotePreview, type Segment } from "@/lib/api";
import { cn } from "@/lib/utils";

function readProfile(params: URLSearchParams): Profile | null {
  const segment = params.get("segment") as Segment | null;
  const tier = Number(params.get("city_tier"));
  const employees = Number(params.get("employees"));
  const sites = Number(params.get("sites"));
  if (!segment || !(tier === 1 || tier === 2) || !(employees >= 1) || !(sites >= 1)) return null;
  return { segment, city_tier: tier, employees, sites, gstin: params.get("gstin") || null };
}

function QuoteView() {
  const t = useTranslations("quote");
  const params = useSearchParams();
  const profile = readProfile(params);
  const key = params.toString();

  const [data, setData] = useState<QuotePreview | null>(null);
  const [error, setError] = useState(false);
  const [selected, setSelected] = useState(0);

  const load = useCallback(() => {
    if (!profile) return;
    setError(false);
    setData(null);
    api
      .previewQuote(profile)
      .then((d) => {
        setData(d);
        // Open on the middle plan when there is one.
        setSelected(Math.min(1, d.tiers.length - 1));
      })
      .catch(() => setError(true));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => {
    load();
  }, [load]);

  if (!profile) {
    return (
      <div className="flex flex-col gap-4 pt-4">
        <p>{t("no_profile")}</p>
        <ButtonLink href="/chat">{t("to_advisor")}</ButtonLink>
      </div>
    );
  }

  if (error) {
    return (
      <div role="alert" className="flex flex-col gap-4 rounded-bill border border-alert/40 bg-surface p-4">
        <p>{t("error")}</p>
        <Button variant="quiet" onClick={load}>
          {t("retry")}
        </Button>
      </div>
    );
  }

  if (!data) {
    return (
      <p aria-busy className="animate-pulse text-ink-soft">
        {t("loading")}
      </p>
    );
  }

  const bundle = data.tiers[selected];

  return (
    <div className="flex flex-col gap-5">
      <h1 className="text-2xl font-semibold">{t("title")}</h1>

      <div role="radiogroup" aria-label={t("title")} className="grid grid-flow-col gap-1 rounded-bill bg-line/60 p-1">
        {data.tiers.map((b, i) => (
          <button
            key={b.tier}
            role="radio"
            aria-checked={i === selected}
            onClick={() => setSelected(i)}
            className={cn(
              "relative min-h-11 cursor-pointer rounded-[4px] px-2 text-sm font-medium transition-colors",
              i === selected ? "bg-surface text-ink shadow-sm" : "text-ink-soft hover:text-ink",
            )}
          >
            {t(b.tier as "good" | "better" | "best")}
            {b.tier === "better" && (
              <span aria-hidden className="absolute right-1.5 top-1.5 size-2 rounded-full bg-marigold" />
            )}
          </button>
        ))}
      </div>

      <Bill bundle={bundle} />

      {!data.gstin_active && <p className="text-sm text-ink-soft">{t("gst_note")}</p>}

      <ButtonLink href="/kyc" width="full">
        {t("accept")}
      </ButtonLink>
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
