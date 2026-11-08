"use client";

import { ArrowLeftRight, Minus, Plus, UserRound } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { RepairChange, RepairOption, RepairResult } from "@/lib/repair";
import { cn, formatINR } from "@/lib/utils";

const RULE_LABEL: Record<string, string> = {
  city_tier: "city tier",
  min_employees: "minimum staff",
  min_sites: "minimum sites",
  requires_gstin: "needs active GST",
  requires_one_of: "needs a base connection",
  budget: "budget",
};

export function RuleBadge({ rule }: { rule: string | null }) {
  if (!rule) return null;
  return (
    <span className="ml-1 inline-flex rounded-[4px] border border-line bg-paper px-1.5 py-px font-mono text-[11px] text-ink-soft">
      {RULE_LABEL[rule] ?? rule}
    </span>
  );
}

function ChangeLine({ c, names }: { c: RepairChange; names: Record<string, string> }) {
  const Icon = c.kind === "add" ? Plus : c.kind === "remove" ? Minus : c.kind === "swap" ? ArrowLeftRight : null;
  const name = names[c.product] ?? c.product;
  const to = c.to ? names[c.to] ?? c.to : null;
  if (c.kind === "profile") {
    return <li className="text-ink-soft">{c.detail}</li>;
  }
  return (
    <li className="flex items-start gap-2">
      {Icon && <Icon aria-hidden className={cn("mt-0.5 size-3.5 shrink-0", c.kind === "remove" ? "text-alert" : "text-pen")} />}
      <span>
        <span className="font-medium">
          {name}
          {to && ` → ${to}`}
        </span>
        {c.kind === "qty" ? `: ${c.detail}` : ` · ${c.detail}`}
        <RuleBadge rule={c.rule} />
      </span>
    </li>
  );
}

/** Problems + options with their changes. Used by the owner what-if and the judge panel. */
export function RepairOptions({
  result,
  currentTotal,
  budget,
  onChoose,
  busy,
  chooseLabel = "Use this plan",
  audit,
}: {
  result: RepairResult;
  currentTotal: number;
  budget?: number | null;
  onChoose?: (o: RepairOption) => void;
  busy?: boolean;
  chooseLabel?: string;
  audit?: { option: string; ineligible: string[]; dependencies_ok: boolean }[];
}) {
  const names: Record<string, string> = { ...(result.names ?? {}) };
  for (const o of result.options) for (const l of o.lines) names[l.product_id] = l.name;
  for (const p of result.problems) if (p.product && !names[p.product]) names[p.product] = p.product;

  return (
    <div className="flex flex-col gap-4">
      <p role="status" className="rounded-bill border border-line bg-surface p-3 text-sm">
        {result.summary}
      </p>
      {result.problems.length > 0 && (
        <ul className="flex flex-col gap-1 text-sm">
          {result.problems.map((p, i) => (
            <li key={i} className="text-ink-soft">
              {p.message}
              <RuleBadge rule={p.rule} />
            </li>
          ))}
        </ul>
      )}
      <ol className="flex flex-col gap-3">
        {result.options.map((o) => {
          const recommended = o.id === result.recommended;
          const delta = o.monthly_total - currentTotal;
          const check = audit?.find((a) => a.option === o.id);
          return (
            <li
              key={o.id}
              className={cn("rounded-bill border bg-surface p-4", recommended ? "border-pen" : "border-line")}
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="font-semibold">
                  {o.label}
                  {recommended && (
                    <span className="ml-2 inline-flex items-center gap-1 text-xs font-medium text-marigold">
                      <span aria-hidden className="size-2 rounded-full bg-marigold" /> Recommended
                    </span>
                  )}
                </p>
                {o.kind !== "handoff" && (
                  <p className="money text-right">
                    <span className="text-lg font-semibold">{formatINR(o.monthly_total)}</span>
                    <span className="text-sm text-ink-soft">/mo</span>
                    <span className={cn("ml-2 text-sm", delta > 0 ? "text-alert" : "text-stamp")}>
                      {delta === 0 ? "no change" : `${delta > 0 ? "+" : "−"}${formatINR(Math.abs(delta))}`}
                    </span>
                  </p>
                )}
              </div>
              {o.kind !== "handoff" && budget != null && (
                <p className={cn("mt-1 text-xs", o.fits_budget ? "text-stamp" : "text-alert")}>
                  {o.fits_budget ? `Within your ${formatINR(budget)} budget` : `Over your ${formatINR(budget)} budget`}
                  {o.setup_total > 0 && <span className="text-ink-soft"> · setup {formatINR(o.setup_total)}</span>}
                </p>
              )}
              {o.kind === "handoff" && (
                <p className="mt-1 flex items-center gap-1.5 text-sm text-ink-soft">
                  <UserRound aria-hidden className="size-4" /> A specialist calls to plan the site; nothing is lost.
                </p>
              )}
              <ul className="mt-3 flex flex-col gap-1.5 text-sm">
                {o.changes.map((c, i) => (
                  <ChangeLine key={i} c={c} names={names} />
                ))}
              </ul>
              {o.unmet.length > 0 && (
                <p className="mt-2 text-sm text-alert">
                  Not included: {o.unmet.map((p) => names[p] ?? p).join(", ")}
                </p>
              )}
              {o.kind !== "handoff" && (
                <p className="mt-2 text-xs text-ink-soft">{o.lines.map((l) => `${l.name} × ${l.qty}`).join(" · ")}</p>
              )}
              {check && (
                <p className="mt-2 text-xs font-medium text-stamp">
                  Rules engine re-check: {check.ineligible.length === 0 ? "0 ineligible products" : `ineligible ${check.ineligible.join(", ")}`},
                  dependencies {check.dependencies_ok ? "OK" : "broken"}
                </p>
              )}
              {onChoose && (
                <Button
                  variant={recommended ? "primary" : "quiet"}
                  className="mt-3 min-h-10 text-sm"
                  disabled={busy}
                  onClick={() => onChoose(o)}
                >
                  {o.kind === "handoff" ? "Ask a specialist" : chooseLabel}
                </Button>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
