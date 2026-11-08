"use client";

import { useLocale, useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";

import { CheckList, ResultIcon } from "@/components/kyc/check-list";
import { DocumentRow } from "@/components/kyc/document-row";
import { Button, ButtonLink } from "@/components/ui/button";
import { api, ApiError, type KycCase, type KycStatus, type Segment } from "@/lib/api";
import { owner } from "@/lib/journey";
import { cn } from "@/lib/utils";

// The owner session (from checkout, or opened here) lives for this tab only.
// Replaced by OTP login + JWT later.
const loadCase = (): KycCase | null => owner.get();
const saveCase = (c: KycCase | null) => owner.set(c);

function KycView() {
  const t = useTranslations("kyc");
  const locale = useLocale();
  const params = useSearchParams();

  const [kycCase, setKycCase] = useState<KycCase | null>(null);
  const [status, setStatus] = useState<KycStatus | null>(null);
  const [consented, setConsented] = useState(false);
  const [marketing, setMarketing] = useState(false);
  const [gstin, setGstin] = useState(params.get("gstin") ?? "");
  const [udyam, setUdyam] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const orderId = params.get("order");
  const refresh = useCallback(async (c: KycCase) => {
    try {
      const st = await api.kycStatus(c);
      setStatus(st);
      if (!st.consent.kyc) setKycCase(null); // owner known, consent not yet given
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        // Token no longer valid (e.g. DB reset): start over.
        saveCase(null);
        setKycCase(null);
        setStatus(null);
      } else {
        setError(String(e));
      }
    }
  }, []);

  useEffect(() => {
    const c = loadCase();
    if (c) {
      setKycCase(c);
      void refresh(c);
    }
  }, [refresh]);
  // While documents are being read, poll until the checks land.
  useEffect(() => {
    if (!kycCase || status?.overall !== "processing") return;
    const id = window.setTimeout(() => void refresh(kycCase), 2000);
    return () => window.clearTimeout(id);
  }, [kycCase, status, refresh]);
  // Read after mount: sessionStorage doesn't exist on the server render.
  const [known, setKnown] = useState(false);
  useEffect(() => setKnown(loadCase() !== null), [kycCase, status]);

  const segment = params.get("segment") as Segment | null;
  const profile =
    segment && params.get("city_tier")
      ? {
          segment,
          city_tier: Number(params.get("city_tier")) as 1 | 2,
          employees: Number(params.get("employees") || 1),
          sites: Number(params.get("sites") || 1),
        }
      : null;

  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const agree = () =>
    run(async () => {
      const existing = loadCase();
      if (!existing && !profile) return;
      const c = existing
        ? await api.giveConsent({ kyc: true, marketing, language: locale, business_id: existing.businessId }, existing)
        : await api.giveConsent({ kyc: true, marketing, language: locale, profile: profile! });
      saveCase(c);
      setKycCase(c);
      setNotice(null);
      await refresh(c);
    });

  const checkIdentity = () =>
    run(async () => {
      if (!kycCase) return;
      await api.setIdentity(kycCase, { gstin: gstin.trim() || null, udyam_number: udyam.trim() || null });
      await refresh(kycCase);
    });

  const withdraw = () =>
    run(async () => {
      if (!kycCase || !window.confirm(t("withdraw_confirm"))) return;
      await api.withdrawConsent(kycCase, "kyc");
      setKycCase(null);
      setStatus(null);
      setConsented(false);
      setNotice(t("withdrawn"));
    });

  // --- step 1: consent ------------------------------------------------------
  if (!kycCase) {
    return (
      <div className="flex flex-col gap-6">
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
        {notice && (
          <p role="status" className="rounded-bill border border-line bg-surface p-3 text-sm">
            {notice}
          </p>
        )}
        <section className="rounded-bill border border-line bg-surface p-4">
          <h2 className="font-semibold">{t("consent_title")}</h2>
          <p className="mt-2 text-sm text-ink-soft">{t("consent_body")}</p>
          <div className="mt-4 flex flex-col gap-3 text-sm">
            <label className="flex min-h-11 cursor-pointer items-start gap-3">
              <input
                type="checkbox"
                checked={consented}
                onChange={(e) => setConsented(e.target.checked)}
                className="mt-0.5 size-5 accent-[rgb(var(--pen))]"
              />
              {t("consent_required")}
            </label>
            <label className="flex min-h-11 cursor-pointer items-start gap-3">
              <input
                type="checkbox"
                checked={marketing}
                onChange={(e) => setMarketing(e.target.checked)}
                className="mt-0.5 size-5 accent-[rgb(var(--pen))]"
              />
              {t("consent_marketing")}
            </label>
          </div>
        </section>
        {error && (
          <p role="alert" className="text-sm text-alert">
            {error}
          </p>
        )}
        {profile || known ? (
          <Button width="full" disabled={!consented || busy} onClick={agree}>
            {t("agree")}
          </Button>
        ) : (
          <div className="flex flex-col gap-3">
            <p className="text-sm text-ink-soft">{t("need_price")}</p>
            <ButtonLink href="/chat" variant="quiet">
              {t("to_quote")}
            </ButtonLink>
          </div>
        )}
      </div>
    );
  }

  // --- step 2+3: identity and documents -------------------------------------
  const hasIdentity = Boolean(status?.gstin || status?.udyam_number);
  const docsByType = new Map(status?.documents.map((d) => [d.doc_type, d]));

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">{t("title")}</h1>

      {status && hasIdentity && (
        <p
          role="status"
          className={cn(
            "flex items-start gap-2 rounded-bill border p-3 text-sm",
            status.overall === "fail" ? "border-alert/40 bg-surface" : "border-line bg-surface",
          )}
        >
          {status.overall !== "incomplete" && <ResultIcon result={status.overall} className="mt-0.5" />}
          {t(`overall.${status.overall}`)}
        </p>
      )}

      <section className="flex flex-col gap-3">
        <h2 className="font-semibold">{t("identity_title")}</h2>
        <div className="flex flex-col gap-1">
          <label htmlFor="gstin" className="text-sm font-medium">
            {t("gstin_label")}
          </label>
          <input
            id="gstin"
            value={gstin}
            onChange={(e) => setGstin(e.target.value.toUpperCase())}
            maxLength={15}
            autoComplete="off"
            spellCheck={false}
            aria-describedby="gstin-help"
            placeholder={status?.gstin ?? undefined}
            className="money min-h-12 rounded-bill border border-line bg-surface px-4 tracking-wide"
          />
          <p id="gstin-help" className="text-xs text-ink-soft">
            {status?.gstin ? t("on_file", { value: status.gstin }) : t("gstin_help")}
          </p>
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="udyam" className="text-sm font-medium">
            {t("udyam_label")}
          </label>
          <input
            id="udyam"
            value={udyam}
            onChange={(e) => setUdyam(e.target.value.toUpperCase())}
            maxLength={19}
            autoComplete="off"
            spellCheck={false}
            aria-describedby="udyam-help"
            placeholder={status?.udyam_number ?? undefined}
            className="money min-h-12 rounded-bill border border-line bg-surface px-4 tracking-wide"
          />
          <p id="udyam-help" className="text-xs text-ink-soft">
            {status?.udyam_number ? t("on_file", { value: status.udyam_number }) : t("udyam_help")}
          </p>
        </div>
        <Button variant="quiet" disabled={busy || (!gstin.trim() && !udyam.trim())} onClick={checkIdentity}>
          {busy ? t("checking") : t("check_identity")}
        </Button>
        {status && hasIdentity && (
          <div className="text-sm">
            {status.name && <p className="font-medium">{t("registered_to", { name: status.name })}</p>}
            <CheckList checks={status.identity.checks} />
          </div>
        )}
      </section>

      {error && (
        <p role="alert" className="text-sm text-alert">
          {error}
        </p>
      )}

      <section className="flex flex-col gap-3">
        <div>
          <h2 className="font-semibold">{t("docs_title")}</h2>
          <p className="text-sm text-ink-soft">{hasIdentity ? t("docs_help") : t("docs_after_identity")}</p>
        </div>
        {status && hasIdentity && (
          <ul className="flex flex-col gap-2">
            {status.required.map((d) => (
              <DocumentRow
                key={d}
                kycCase={kycCase}
                docType={d}
                doc={docsByType.get(d)}
                onUploaded={() => refresh(kycCase)}
              />
            ))}
          </ul>
        )}
      </section>

      {status && status.missing.length === 0 && status.overall !== "fail" && (
        <ButtonLink href={orderId ? `/track/${orderId}` : "/"} width="full">
          {t("continue")}
        </ButtonLink>
      )}

      <Button variant="link" className="self-start text-sm text-ink-soft" onClick={withdraw} disabled={busy}>
        {t("withdraw")}
      </Button>
    </div>
  );
}

export default function KycPage() {
  return (
    <Suspense>
      <KycView />
    </Suspense>
  );
}
