"use client";

import { Check, PauseCircle } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";

import { Button, ButtonLink } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { orders, owner, type OrderView } from "@/lib/journey";
import { cn } from "@/lib/utils";

const POLL_MS = 15000;

function TrackView({ orderId }: { orderId: number }) {
  const t = useTranslations("track");
  const format = useFormatter();
  const params = useSearchParams();
  const [token, setToken] = useState<string | null | undefined>(undefined); // undefined = not read yet
  useEffect(() => setToken(params.get("t") ?? owner.get()?.token ?? null), [params]);

  const [order, setOrder] = useState<OrderView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [slot, setSlot] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      setOrder(await orders.get(orderId, token));
    } catch (e) {
      setError(e instanceof ApiError && e.status === 404 ? t("not_found") : t("error"));
    }
  }, [orderId, token, t]);

  useEffect(() => {
    void load();
    const id = window.setInterval(load, POLL_MS);
    return () => window.clearInterval(id);
  }, [load]);

  async function reschedule() {
    if (!token || !slot) return;
    setBusy(true);
    try {
      setOrder(await orders.reschedule(orderId, token, slot));
      setSlot("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("error"));
    } finally {
      setBusy(false);
    }
  }

  const when = (iso: string) =>
    format.dateTime(new Date(iso), { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });

  if (token === undefined) return <p className="animate-pulse text-ink-soft">{t("loading")}</p>;
  if (!token || error) {
    return (
      <div className="flex flex-col gap-4">
        <p role="alert">{error ?? t("not_found")}</p>
        <ButtonLink href="/start" variant="quiet">
          {t("home")}
        </ButtonLink>
      </div>
    );
  }
  if (!order) return <p className="animate-pulse text-ink-soft">{t("loading")}</p>;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
        <p className="text-sm text-ink-soft">#{order.id}</p>
      </div>

      {order.eta_date && order.state !== "activated" && (
        <p className="rounded-bill border border-line bg-surface p-3">
          {t("eta")}{" "}
          <strong>{format.dateTime(new Date(order.eta_date), { day: "numeric", month: "long", year: "numeric" })}</strong>
        </p>
      )}
      {order.state === "on_hold" && (
        <p role="status" className="flex items-start gap-2 rounded-bill border border-marigold/60 bg-surface p-3 text-sm">
          <PauseCircle aria-hidden className="mt-0.5 size-4 shrink-0 text-marigold" />
          {t("on_hold", { reason: order.hold_reason ?? "" })}
        </p>
      )}

      <ol className="flex flex-col">
        {order.steps.map((s, i) => (
          <li key={s.state} className="relative flex gap-4 pb-6 last:pb-0">
            {i < order.steps.length - 1 && (
              <span
                aria-hidden
                className={cn("absolute left-[11px] top-7 h-[calc(100%-1.5rem)] w-0.5", s.done && !s.current ? "bg-stamp" : "bg-line")}
              />
            )}
            <span
              className={cn(
                "z-10 flex size-6 shrink-0 items-center justify-center rounded-full border-2",
                s.done && !s.current && "border-stamp bg-stamp text-white",
                s.current && "border-pen bg-surface",
                !s.done && "border-line bg-surface",
              )}
            >
              {s.done && !s.current && <Check aria-hidden className="size-3.5" strokeWidth={3} />}
            </span>
            <div className="pt-0.5">
              <p className={cn(s.current ? "font-semibold text-pen" : s.done ? "" : "text-ink-soft")}>
                {t(`states.${s.state}`)}
              </p>
              {s.at && <p className="text-xs text-ink-soft">{when(s.at)}</p>}
              {s.state === "engineer_scheduled" && order.engineer_slot && (
                <p className="text-sm">{t("visit", { when: when(order.engineer_slot) })}</p>
              )}
            </div>
          </li>
        ))}
      </ol>

      {order.slot_options.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="font-semibold">{order.engineer_slot ? t("move_visit") : t("pick_visit")}</h2>
          <label htmlFor="slot" className="sr-only">
            {t("pick_visit")}
          </label>
          <select
            id="slot"
            value={slot}
            onChange={(e) => setSlot(e.target.value)}
            className="min-h-12 cursor-pointer rounded-bill border border-line bg-surface px-3"
          >
            <option value="">{t("choose_slot")}</option>
            {order.slot_options.map((o) => (
              <option key={o.start} value={o.start}>
                {when(o.start)} – {format.dateTime(new Date(o.end), { hour: "numeric", minute: "2-digit" })}
              </option>
            ))}
          </select>
          <Button variant="quiet" disabled={!slot || busy} onClick={reschedule}>
            {t("confirm_slot")}
          </Button>
        </section>
      )}

      <section>
        <h2 className="font-semibold">{t("whats_coming")}</h2>
        <ul className="mt-2 flex flex-col gap-1 text-sm">
          {order.items.map((i) => (
            <li key={i.name} className="flex justify-between gap-3">
              <span>{i.name}</span>
              <span className="text-ink-soft">{t("days", { count: i.install_days })}</span>
            </li>
          ))}
        </ul>
      </section>

      <p className="text-xs text-ink-soft">{t("updates_note")}</p>
    </div>
  );
}

export default function TrackPage({ params }: { params: { orderId: string } }) {
  return (
    <Suspense>
      <TrackView orderId={Number(params.orderId)} />
    </Suspense>
  );
}
