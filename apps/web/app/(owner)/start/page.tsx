import { useTranslations } from "next-intl";

import { ButtonLink } from "@/components/ui/button";

export default function Home() {
  const t = useTranslations("home");
  const facts = [
    { n: "5", label: t("facts.questions") },
    { n: "4", label: t("facts.kyc") },
    { n: "0", label: t("facts.visits") },
  ];

  return (
    <div className="flex flex-1 flex-col justify-between gap-10 pt-6">
      <section>
        <h1 className="text-[2rem] font-semibold leading-tight tracking-tight text-balance">{t("title")}</h1>
        <p className="mt-4 max-w-[60ch] text-ink-soft">{t("body")}</p>
      </section>

      <dl className="grid grid-cols-3 border-y border-line py-4">
        {facts.map((f) => (
          <div key={f.label} className="pr-3">
            <dt className="money text-3xl font-semibold text-pen">{f.n}</dt>
            <dd className="mt-1 text-sm leading-snug text-ink-soft">{f.label}</dd>
          </div>
        ))}
      </dl>

      <div className="flex flex-col gap-2">
        <ButtonLink href="/chat" width="full">
          {t("start")}
        </ButtonLink>
        <ButtonLink href="/quote?segment=micro&city_tier=1&employees=4&sites=1" variant="quiet" width="full">
          {t("skip")}
        </ButtonLink>
      </div>
    </div>
  );
}
