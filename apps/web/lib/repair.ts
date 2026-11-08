/** Quote repair (owner what-if) and the judge challenge panel. */

import { request } from "@/lib/api";
import type { OwnerSession, Quote } from "@/lib/journey";

export interface RepairChange {
  kind: "add" | "remove" | "swap" | "qty" | "profile";
  product: string;
  detail: string;
  rule: string | null;
  to: string | null;
}

export interface RepairOption {
  id: string;
  kind: "repaired" | "within_budget" | "keep_must_haves" | "fit_budget" | "alternative" | "handoff";
  label: string;
  items: Record<string, number>;
  lines: { product_id: string; name: string; qty: number }[];
  monthly_total: number;
  setup_total: number;
  contract_months: number;
  eta_days: number;
  fits_budget: boolean;
  changes: RepairChange[];
  unmet: string[];
}

export interface RepairResult {
  problems: { rule: string; product: string | null; message: string }[];
  options: RepairOption[];
  recommended: string | null;
  needs_choice: boolean;
  summary: string;
  names?: Record<string, string>;
}

export interface WhatIf {
  budget?: number | null;
  must_have?: string[];
  add?: string[];
  remove?: string[];
  sites?: number | null;
  city_tier?: 1 | 2 | null;
  gstin_active?: false | null;
  connection?: string | null;
}

const headers = (s: OwnerSession) => ({ "X-Owner-Token": s.token });

export const repairApi = {
  whatIf: (quoteId: number, s: OwnerSession, body: WhatIf) =>
    request<RepairResult & { current_total: number }>(`/quotes/${quoteId}/what-if`, {
      method: "POST",
      headers: headers(s),
      body: JSON.stringify(body),
    }),
  apply: (quoteId: number, s: OwnerSession, body: WhatIf & { option_id: string }) =>
    request<Quote | { handoff: true; message: string }>(`/quotes/${quoteId}/what-if/apply`, {
      method: "POST",
      headers: headers(s),
      body: JSON.stringify(body),
    }),
};

// --- judge -------------------------------------------------------------------

export interface JudgeProfile {
  segment: "micro" | "prof" | "multi" | "mfg";
  city_tier: 1 | 2;
  employees: number;
  sites: number;
  gstin_active: boolean;
}

export interface RuleRow {
  product_id: string;
  name: string;
  category: string;
  eligible: boolean;
  rules: string[];
  reasons: string[];
  needs_one_of: string[];
}

export interface JudgePlan {
  tiers: {
    tier: string;
    items: { product_id: string; name: string; qty: number; unit_price: number; monthly: number }[];
    monthly_total: number;
    setup_total: number;
  }[];
  rules: RuleRow[];
}

export interface Scorecard {
  available: boolean;
  generated_at?: string;
  seconds?: number;
  lead_sweep?: { profiles: number; plans_checked: number; ineligible_plans: number; broken_dependencies: number };
  personas?: { total: number; passed: number; max_turns: number; failures: { id: string; issues: string[] }[] };
  repair?: {
    cases: number;
    invalid_options: number;
    solvable_within_budget: number;
    valid_fix_found: number;
    handoffs_offered: number;
  };
  kyc?: {
    correct: number;
    total: number;
    applicants: { applicant: string; finding: string; expected: string; actual: string; reason: string; ok: boolean }[];
  };
}

export const judgeApi = {
  scenarios: () =>
    request<{ id: string; label: string; profile: JudgeProfile; try: string }[]>("/judge/scenarios"),
  plan: (profile: JudgeProfile) =>
    request<JudgePlan>("/judge/plan", { method: "POST", body: JSON.stringify(profile) }),
  challenge: (profile: JudgeProfile, items: Record<string, number>, change: WhatIf, employees?: number | null) =>
    request<
      RepairResult & {
        before_total: number;
        audit: { option: string; ineligible: string[]; dependencies_ok: boolean }[];
        rules_after: RuleRow[];
      }
    >("/judge/challenge", { method: "POST", body: JSON.stringify({ profile, items, change, employees }) }),
  scorecard: () => request<Scorecard>("/judge/scorecard"),
};

export const PRIMARY_CONNECTIONS = [
  { id: "P01", name: "Biz Fibre 100" },
  { id: "P02", name: "Biz Fibre 300" },
  { id: "P03", name: "Biz Fibre 1G" },
  { id: "P04", name: "Biz 5G AirFiber 100" },
  { id: "P05", name: "Internet Leased Line 20" },
  { id: "P06", name: "Internet Leased Line 100" },
];
