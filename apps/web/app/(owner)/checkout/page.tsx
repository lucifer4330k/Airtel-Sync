"use client";

import { useTranslations } from "next-intl";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Button, ButtonLink } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { lastOrder, owner, quotes as quoteApi, type Quote } from "@/lib/journey";
import { cn, formatINR } from "@/lib/utils";

const PHONE = /^(\+91)?[6-9]\d{9}$/;
const UPI = /^[\w.-]{2,}@[a-zA-Z]{2,}$/;

function CheckoutView() {
  const t = useTranslations("checkout");
  const router = useRouter();
  const params = useSearchParams();
  const quoteId = Number(params.get("q"));

  const [quote, setQuote] = useState<Quote | null>(null);
  const [phone, setPhone] = useState("");
  const [method, setMethod] = useState<"upi_autopay" | "razorpay">("upi_autopay");
  const [upi, setUpi] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const s = owner.get();
    if (!s || !quoteId) return;
    quoteApi.get(quoteId, s).then(setQuote).catch(() => setError(t("load_error")));
  }, [quoteId, t]);

  const phoneOk = PHONE.test(phone.replace(/\s/g, ""));
  const upiOk = method !== "upi_autopay" || upi === "" || UPI.test(upi);

  async function pay() {
    const s = owner.get();
    if (!s || !quote) return;
    setBusy(true);
    setError(null);
    try {
      const res = await quoteApi.accept(quote.id, s, {
        phone: phone.replace(/\s/g, ""),
        payment_method: method,
        upi_id: method === "upi_autopay" && upi ? upi : undefined,
      });
      lastOrder.set(res.order_id);
      router.push(`/kyc?order=${res.order_id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("pay_error"));
      setBusy(false);
    }
  }

  const [hasOwner, setHasOwner] = useState<boolean | null>(null);
  useEffect(() => setHasOwner(owner.get() !== null), []);
  if (hasOwner === null) return <p className="animate-pulse text-ink-soft">{t("loading")}</p>;
  if (!hasOwner || !quoteId) {
    return (
      <div className="flex flex-col gap-4 pt-4">
        <p>{t("no_quote")}</p>
        <ButtonLink href="/chat">{t("to_advisor")}</ButtonLink>
      </div>
    );
  }
  if (!quote) {
    return <p className="animate-pulse text-ink-soft">{error ?? t("loading")}</p>;
  }

  return (
    <div className="flex flex-col gap-5">
      <h1 className="text-2xl font-semibold">{t("title")}</h1>

      <dl className="grid grid-cols-2 gap-3 rounded-bill border border-line bg-surface p-4 text-sm">
        <div>
          <dt className="text-ink-soft">{t("monthly")}</dt>
          <dd className="money text-xl font-semibold">{formatINR(quote.monthly_total)}</dd>
        </div>
        <div>
          <dt className="text-ink-soft">{t("today")}</dt>
          <dd className="money text-xl font-semibold">{formatINR(quote.setup_total)}</dd>
        </div>
        <div className="col-span-2 text-ink-soft">{t("contract", { months: quote.contract_months })}</div>
      </dl>

      <div className="flex flex-col gap-1">
        <label htmlFor="phone" className="text-sm font-medium">
          {t("phone")}
        </label>
        <input
          id="phone"
          inputMode="tel"
          autoComplete="tel"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          aria-describedby="phone-help"
          aria-invalid={phone !== "" && !phoneOk}
          className="money min-h-12 rounded-bill border border-line bg-surface px-4"
        />
        <p id="phone-help" className={cn("text-xs", phone !== "" && !phoneOk ? "text-alert" : "text-ink-soft")}>
          {phone !== "" && !phoneOk ? t("phone_invalid") : t("phone_help")}
        </p>
      </div>

      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 text-sm font-medium">{t("method")}</legend>
        {(["upi_autopay", "razorpay"] as const).map((m) => (
          <label
            key={m}
            className={cn(
              "flex min-h-12 cursor-pointer items-start gap-3 rounded-bill border bg-surface p-3",
              method === m ? "border-pen" : "border-line",
            )}
          >
            <input
              type="radio"
              name="method"
              value={m}
              checked={method === m}
              onChange={() => setMethod(m)}
              className="mt-1 size-4 accent-[rgb(var(--pen))]"
            />
            <span>
              <span className="font-medium">{t(`method_${m}`)}</span>
              <span className="block text-sm text-ink-soft">{t(`method_${m}_help`)}</span>
            </span>
          </label>
        ))}
      </fieldset>

      {method === "upi_autopay" && (
        <div className="flex flex-col gap-1">
          <label htmlFor="upi" className="text-sm font-medium">
            {t("upi")}
          </label>
          <input
            id="upi"
            value={upi}
            onChange={(e) => setUpi(e.target.value.trim())}
            autoComplete="off"
            placeholder="name@bank"
            aria-invalid={!upiOk}
            className="min-h-12 rounded-bill border border-line bg-surface px-4"
          />
          {!upiOk && <p className="text-xs text-alert">{t("upi_invalid")}</p>}
        </div>
      )}

      <p className="text-xs text-ink-soft">{t("test_mode")}</p>
      {error && (
        <p role="alert" className="text-sm text-alert">
          {error}
        </p>
      )}
      <Button width="full" disabled={!phoneOk || !upiOk || busy} onClick={pay}>
        {busy ? t("paying") : t("pay", { amount: formatINR(quote.setup_total) })}
      </Button>
    </div>
  );
}

export default function CheckoutPage() {
  return (
    <Suspense>
      <CheckoutView />
    </Suspense>
  );
}
