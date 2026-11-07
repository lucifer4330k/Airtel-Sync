import { Check } from "lucide-react";
import { useTranslations } from "next-intl";

import { cn } from "@/lib/utils";

const STATES = ["placed", "kyc", "scheduled", "installed", "activated"] as const;

// Shell: shows the state machine with a fixed demo position. GET /orders/{id}
// replaces DEMO_POSITION with the live state and event timestamps.
const DEMO_POSITION = 2;

export default function TrackPage({ params }: { params: { orderId: string } }) {
  const t = useTranslations("track");
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
        <p className="text-sm text-ink-soft">#{params.orderId}</p>
      </div>
      <ol className="flex flex-col">
        {STATES.map((s, i) => {
          const done = i < DEMO_POSITION;
          const now = i === DEMO_POSITION;
          return (
            <li key={s} className="relative flex gap-4 pb-6 last:pb-0">
              {i < STATES.length - 1 && (
                <span aria-hidden className={cn("absolute left-[11px] top-7 h-[calc(100%-1.5rem)] w-0.5", done ? "bg-stamp" : "bg-line")} />
              )}
              <span
                className={cn(
                  "z-10 flex size-6 shrink-0 items-center justify-center rounded-full border-2",
                  done && "border-stamp bg-stamp text-white",
                  now && "border-pen bg-surface",
                  !done && !now && "border-line bg-surface",
                )}
              >
                {done && <Check aria-hidden className="size-3.5" strokeWidth={3} />}
              </span>
              <p className={cn("pt-0.5", now ? "font-semibold text-pen" : done ? "" : "text-ink-soft")}>
                {t(`states.${s}`)}
              </p>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
