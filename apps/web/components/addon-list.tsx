"use client";

import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import type { AddonOption } from "@/lib/journey";
import { cn, formatINR } from "@/lib/utils";

/** Add-on switches. Blocked options stay visible with a one-line reason. */
export function AddonList({
  options,
  onToggle,
}: {
  options: AddonOption[];
  onToggle: (productId: string, include: boolean) => Promise<string | null>;
}) {
  const t = useTranslations("quote");
  const [pending, setPending] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});

  async function flip(o: AddonOption) {
    setPending(o.product_id);
    const err = await onToggle(o.product_id, !o.included);
    setErrors((e) => {
      const next = { ...e };
      if (err) next[o.product_id] = err;
      else delete next[o.product_id];
      return next;
    });
    setPending(null);
  }

  return (
    <ul className="divide-y divide-line rounded-bill border border-line bg-surface">
      {options.map((o) => {
        const id = `addon-${o.product_id}`;
        const blocked = !o.available;
        return (
          <li key={o.product_id} className="flex items-start gap-3 p-3">
            <div className="min-w-0 flex-1">
              <label htmlFor={id} className={cn("font-medium", blocked && "text-ink-soft")}>
                {o.name}
              </label>
              <p className="text-sm text-ink-soft">{o.description}</p>
              {blocked && o.reason && <p className="mt-1 text-sm text-ink-soft">{o.reason}</p>}
              {errors[o.product_id] && (
                <p role="alert" className="mt-1 text-sm text-alert">
                  {errors[o.product_id]}
                </p>
              )}
            </div>
            <div className="flex shrink-0 flex-col items-end gap-1">
              <span className="money text-sm text-ink-soft">
                {o.included ? t("included") : `+${formatINR(o.monthly_from)}`}
              </span>
              <button
                id={id}
                type="button"
                role="switch"
                aria-checked={o.included}
                disabled={blocked || pending !== null}
                onClick={() => flip(o)}
                className={cn(
                  "relative inline-flex h-7 w-12 cursor-pointer items-center rounded-full transition-colors disabled:cursor-not-allowed disabled:opacity-40",
                  o.included ? "bg-pen" : "bg-line",
                )}
              >
                <span className="sr-only">{o.name}</span>
                {pending === o.product_id ? (
                  <Loader2 aria-hidden className="mx-auto size-4 animate-spin text-white" />
                ) : (
                  <span
                    aria-hidden
                    className={cn(
                      "inline-block size-5 rounded-full bg-white shadow transition-transform",
                      o.included ? "translate-x-6" : "translate-x-1",
                    )}
                  />
                )}
              </button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
