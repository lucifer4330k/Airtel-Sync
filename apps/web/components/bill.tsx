import { useFormatter, useTranslations } from "next-intl";

import type { LineItem, PricedBundle } from "@/lib/api";
import { addDays, formatINR, REFERENCE_DATE } from "@/lib/utils";

// Plain-language quantities: no product codes ever reach the screen.
// per account / number / pack are always one, so they get no quantity line.
const COUNTED_UNITS = new Set(["site", "line", "user", "camera", "device", "channel", "counter", "vehicle", "IP"]);

/** The quote as a shop bill: the one memorable surface of the owner app. */
export function Bill({ bundle }: { bundle: PricedBundle }) {
  const t = useTranslations("quote");
  const tu = useTranslations("units");
  const format = useFormatter();

  function qtyLabel(item: LineItem): string | null {
    const unit = item.unit.replace(/^per /, "");
    return COUNTED_UNITS.has(unit) ? tu(unit as "site", { count: item.qty }) : null;
  }
  const activation = addDays(REFERENCE_DATE, bundle.eta_days);

  return (
    <article className="rounded-bill border border-line bg-surface">
      <ul className="divide-y divide-dashed divide-line px-4">
        {bundle.items.map((item) => (
          <li key={item.product_id} className="flex items-baseline justify-between gap-4 py-3">
            <div>
              <p className="font-medium">{item.name}</p>
              {qtyLabel(item) && (
                <p className="text-sm text-ink-soft">
                  {qtyLabel(item)} × <span className="money">{formatINR(item.unit_price)}</span>
                </p>
              )}
            </div>
            <span className="money shrink-0">{formatINR(item.monthly)}</span>
          </li>
        ))}
      </ul>

      <div className="border-t-2 border-ink px-4 pb-4 pt-3">
        <p className="money text-[2.75rem] font-semibold leading-none tracking-tight">
          {formatINR(bundle.monthly_total)}
        </p>
        <p className="mt-1 text-sm text-ink-soft">{t("per_month")}</p>

        <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
          <div>
            <dt className="text-ink-soft">{t("setup")}</dt>
            <dd className="money font-medium">{formatINR(bundle.setup_total)}</dd>
          </div>
          <div>
            <dt className="text-ink-soft">{t("contract")}</dt>
            <dd className="font-medium">{t("months", { count: bundle.contract_months })}</dd>
          </div>
          <div className="col-span-2">
            <dt className="text-ink-soft">{t("activation")}</dt>
            <dd className="font-medium">{format.dateTime(activation, { day: "numeric", month: "long", year: "numeric" })}</dd>
          </div>
        </dl>
      </div>
    </article>
  );
}
