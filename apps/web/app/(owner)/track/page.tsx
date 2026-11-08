"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ButtonLink } from "@/components/ui/button";
import { lastOrder } from "@/lib/journey";

/** "Track" step: jump to this tab's latest order, if there is one. */
export default function TrackIndex() {
  const t = useTranslations("track");
  const router = useRouter();
  const [none, setNone] = useState(false);

  useEffect(() => {
    const id = lastOrder.get();
    if (id) router.replace(`/track/${id}`);
    else setNone(true);
  }, [router]);

  if (!none) return null;
  return (
    <div className="flex flex-col gap-4 pt-4">
      <p>{t("not_found")}</p>
      <ButtonLink href="/chat" variant="quiet">
        {t("home")}
      </ButtonLink>
    </div>
  );
}
