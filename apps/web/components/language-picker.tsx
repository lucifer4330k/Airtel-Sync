"use client";

import { Languages } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";

import { LOCALE_COOKIE, LOCALE_LABELS, LOCALES, type Locale } from "@/i18n/locales";

export function LanguagePicker() {
  const t = useTranslations("app");
  const locale = useLocale() as Locale;
  const router = useRouter();

  function choose(next: Locale) {
    document.cookie = `${LOCALE_COOKIE}=${next}; path=/; max-age=31536000; samesite=lax`;
    router.refresh();
  }

  return (
    <label className="flex min-h-11 items-center gap-2 text-sm text-ink-soft">
      <Languages aria-hidden className="size-4" />
      <span className="sr-only">{t("language")}</span>
      <select
        value={locale}
        onChange={(e) => choose(e.target.value as Locale)}
        className="cursor-pointer rounded-bill border border-line bg-surface px-2 py-1.5 text-ink"
      >
        {LOCALES.map((l) => (
          <option key={l} value={l}>
            {LOCALE_LABELS[l]}
          </option>
        ))}
      </select>
    </label>
  );
}
