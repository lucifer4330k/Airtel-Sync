"use client";

import { useTranslations } from "next-intl";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { ButtonLink } from "@/components/ui/button";
import { owner, plan, quotes } from "@/lib/journey";

/** Opens a plan from a WhatsApp link: /resume?b=<business>&t=<owner token>&q=<quote>. */
function Resume() {
  const t = useTranslations("quote");
  const router = useRouter();
  const params = useSearchParams();
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const businessId = Number(params.get("b"));
    const token = params.get("t");
    const quoteId = Number(params.get("q"));
    if (!businessId || !token || !quoteId) {
      setFailed(true);
      return;
    }
    const session = { businessId, token };
    quotes
      .get(quoteId, session)
      .then((q) => {
        owner.set(session);
        plan.set({ quoteIds: q.siblings ?? [q.id], recommended: quoteId });
        router.replace(`/quote?q=${quoteId}`);
      })
      .catch(() => setFailed(true));
  }, [params, router]);

  if (!failed) return <p className="animate-pulse text-ink-soft">{t("loading")}</p>;
  return (
    <div className="flex flex-col gap-4 pt-4">
      <p>{t("no_profile")}</p>
      <ButtonLink href="/chat">{t("to_advisor")}</ButtonLink>
    </div>
  );
}

export default function ResumePage() {
  return (
    <Suspense>
      <Resume />
    </Suspense>
  );
}
