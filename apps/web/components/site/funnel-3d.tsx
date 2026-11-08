import { type CSSProperties } from "react";

import { cn } from "@/lib/utils";

import s from "./landing.module.css";

/*
 * smb_leads.csv, April to June 2026: where each of the 5,000 leads stopped and
 * the drop reason recorded. Each box's width is the share of leads still in;
 * its red end is the share lost at that stage, so the next box starts exactly
 * where the red begins. `process` marks reasons a phone journey removes:
 * a visit, a wait or paperwork.
 */
type Reason = { text: string; n: number; process?: boolean };
type Stage = { name: string; count: number; reasons: Reason[] };

const STAGES: Stage[] = [
  {
    name: "Asked to be contacted",
    count: 5000,
    reasons: [
      { text: "unreachable after 3 calls", n: 805 },
      { text: "not interested on the first call", n: 470 },
      { text: "wrong number", n: 319 },
    ],
  },
  {
    name: "Reached by phone",
    count: 3406,
    reasons: [
      { text: "no time for a sales visit", n: 531, process: true },
      { text: "locked in with their provider", n: 325 },
      { text: "visit never scheduled", n: 296, process: true },
      { text: "only wanted a mobile plan", n: 280 },
    ],
  },
  {
    name: "Needs assessed",
    count: 1974,
    reasons: [
      { text: "price too high", n: 414 },
      { text: "competitor cheaper", n: 207 },
      { text: "quote too complex", n: 206, process: true },
      { text: "quote took too long", n: 179, process: true },
      { text: "decided to wait", n: 107 },
    ],
  },
  {
    name: "Quote accepted",
    count: 861,
    reasons: [
      { text: "missing GST or Udyam document", n: 94, process: true },
      { text: "paperwork too long", n: 79, process: true },
      { text: "signatory not available", n: 53, process: true },
      { text: "details didn't match", n: 47, process: true },
    ],
  },
  {
    name: "Documents complete",
    count: 588,
    reasons: [
      { text: "install delayed past 21 days", n: 98, process: true },
      { text: "cancelled before install", n: 53 },
      { text: "site not feasible", n: 41 },
      { text: "first payment failed", n: 28, process: true },
    ],
  },
  { name: "Connected and working", count: 368, reasons: [] },
];

const TOTAL = STAGES[0].count;
const fmt = (n: number) => n.toLocaleString("en-IN");

export const PROCESS_LOST = STAGES.flatMap((st) => st.reasons)
  .filter((r) => r.process)
  .reduce((sum, r) => sum + r.n, 0);

export function Funnel3D() {
  return (
    <ol className="flex flex-col">
      {STAGES.map((st, i) => {
        const next = STAGES[i + 1]?.count ?? st.count;
        const lost = st.count - next;
        const final = i === STAGES.length - 1;
        const style = {
          "--share": ((st.count / TOTAL) * 100).toFixed(2),
          "--keep": ((next / st.count) * 100).toFixed(2),
        } as CSSProperties;
        return (
          <li
            key={st.name}
            className={cn(
              s.row,
              "grid gap-x-10 gap-y-3 border-t border-line py-5 md:grid-cols-[minmax(0,1fr)_minmax(0,25rem)]",
            )}
          >
            <div className={cn(s.slabCell, "pt-4 md:pt-5")} aria-hidden>
              <div className={cn(s.slab, final && s.slabFinal)} style={style} />
            </div>
            <div>
              <p className="flex items-baseline justify-between gap-4">
                <span className="font-medium">{st.name}</span>
                <span className={cn("money font-display text-3xl font-bold tracking-tight", final && "text-stamp")}>
                  {fmt(st.count)}
                </span>
              </p>
              {lost > 0 && (
                <p className="mt-1 text-sm leading-relaxed text-ink-soft">
                  <span className="money font-semibold text-alert">{fmt(lost)} left here:</span>{" "}
                  {st.reasons.map((r, j) => (
                    <span key={r.text}>
                      <span className={cn(r.process && "font-semibold text-ink")}>
                        {r.text} <span className="money">{fmt(r.n)}</span>
                      </span>
                      {j < st.reasons.length - 1 ? ", " : ""}
                    </span>
                  ))}
                </p>
              )}
              {final && (
                <p className="mt-1 text-sm text-ink-soft">
                  7.4% of the businesses that asked, after 17.6 days on average.
                </p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
