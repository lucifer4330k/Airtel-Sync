import { CheckCircle2, Clock, Loader2, XCircle } from "lucide-react";

import type { Check, CheckResult } from "@/lib/api";
import { cn } from "@/lib/utils";

const ICON = { pass: CheckCircle2, fail: XCircle, review: Clock } as const;
const TONE: Record<CheckResult, string> = {
  pass: "text-stamp",
  fail: "text-alert",
  review: "text-marigold",
};

export function ResultIcon({ result, className }: { result: CheckResult | "processing"; className?: string }) {
  if (result === "processing") return <Loader2 aria-hidden className={cn("size-4 shrink-0 animate-spin text-ink-soft", className)} />;
  const Icon = ICON[result];
  return <Icon aria-hidden className={cn("size-4 shrink-0", TONE[result], className)} />;
}

/** Reasons in the API's words; passing checks collapse to keep the list short. */
export function CheckList({ checks, showPassed = false }: { checks: Check[]; showPassed?: boolean }) {
  const shown = showPassed ? checks : checks.filter((c) => c.result !== "pass");
  if (shown.length === 0) return null;
  return (
    <ul className="mt-2 flex flex-col gap-1.5 text-sm">
      {shown.map((c) => (
        <li key={c.name} className="flex items-start gap-2">
          <ResultIcon result={c.result} className="mt-0.5" />
          <span className={c.result === "fail" ? "text-ink" : "text-ink-soft"}>{c.reason}</span>
        </li>
      ))}
    </ul>
  );
}
