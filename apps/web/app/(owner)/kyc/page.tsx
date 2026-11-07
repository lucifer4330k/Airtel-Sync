"use client";

import { FileText } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";

const DOCS = ["gst", "udyam", "id", "address"] as const;

// Shell: consent gate + document list. Upload, OCR and live checks
// (POST /kyc/consent, POST /kyc/documents) land in week 2.
export default function KycPage() {
  const t = useTranslations("kyc");
  const [consented, setConsented] = useState(false);

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">{t("title")}</h1>

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
            <input type="checkbox" className="mt-0.5 size-5 accent-[rgb(var(--pen))]" />
            {t("consent_marketing")}
          </label>
        </div>
      </section>

      <ul className="flex flex-col gap-2">
        {DOCS.map((d) => (
          <li key={d} className="flex items-center gap-3 rounded-bill border border-line bg-surface p-3">
            <FileText aria-hidden className="size-5 shrink-0 text-ink-soft" />
            <div className="flex-1">
              <p className="font-medium">{t(`docs.${d}`)}</p>
              <p className="text-sm text-ink-soft">{t("not_uploaded")}</p>
            </div>
            <Button variant="quiet" disabled={!consented} className="min-h-11 px-4 text-sm">
              {t("upload")}
            </Button>
          </li>
        ))}
      </ul>
    </div>
  );
}
