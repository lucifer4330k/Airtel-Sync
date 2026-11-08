"use client";

import { CheckCircle2, XCircle } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { RepairOptions, RuleBadge } from "@/components/repair-options";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import {
  judgeApi,
  PRIMARY_CONNECTIONS,
  type JudgePlan,
  type JudgeProfile,
  type RepairResult,
  type RuleRow,
  type Scorecard,
} from "@/lib/repair";
import { cn, formatINR } from "@/lib/utils";

const SEGMENTS = [
  ["micro", "Shop or service (micro)"],
  ["prof", "Clinic or office (professional)"],
  ["multi", "Several branches (multi-site)"],
  ["mfg", "Factory or workshop (manufacturer)"],
] as const;
const TIER_LABEL: Record<string, string> = { good: "Essential", better: "Recommended", best: "Complete" };
const fmt = new Intl.NumberFormat("en-IN");

type Challenge = RepairResult & {
  before_total: number;
  audit: { option: string; ineligible: string[]; dependencies_ok: boolean }[];
  rules_after: RuleRow[];
};

export default function JudgePage() {
  const [scenarios, setScenarios] = useState<{ id: string; label: string; profile: JudgeProfile; try: string }[]>([]);
  const [scenarioId, setScenarioId] = useState("");
  const [profile, setProfile] = useState<JudgeProfile>({
    segment: "prof",
    city_tier: 1,
    employees: 5,
    sites: 1,
    gstin_active: true,
  });
  const [plan, setPlan] = useState<JudgePlan | null>(null);
  const [tierIdx, setTierIdx] = useState(0);
  const [essential, setEssential] = useState<string[]>([]);
  const [removed, setRemoved] = useState<string[]>([]);
  const [add, setAdd] = useState("");
  const [budget, setBudget] = useState("");
  const [sites, setSites] = useState("");
  const [employees, setEmployees] = useState("");
  const [tier, setTier] = useState("");
  const [noGst, setNoGst] = useState(false);
  const [connection, setConnection] = useState("");
  const [result, setResult] = useState<Challenge | null>(null);
  const [showRules, setShowRules] = useState(false);
  const [score, setScore] = useState<Scorecard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const decisionRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (result) decisionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [result]);

  useEffect(() => {
    judgeApi.scenarios().then(setScenarios).catch(() => setError("The API isn't reachable yet. It may be waking up."));
    judgeApi.scorecard().then(setScore).catch(() => undefined);
  }, []);

  const build = useCallback(async (p: JudgeProfile) => {
    setError(null);
    setResult(null);
    try {
      const res = await judgeApi.plan(p);
      setPlan(res);
      setTierIdx(Math.min(1, res.tiers.length - 1));
      setEssential([]);
      setRemoved([]);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }, []);

  function pickScenario(id: string) {
    const s = scenarios.find((x) => x.id === id);
    if (!s) return;
    setScenarioId(id);
    setProfile(s.profile);
    setBudget("");
    setSites("");
    setEmployees("");
    setTier("");
    setNoGst(false);
    setConnection("");
    setAdd("");
    void build(s.profile);
  }

  async function run() {
    if (!plan) return;
    setBusy(true);
    setError(null);
    const items = Object.fromEntries(plan.tiers[tierIdx].items.map((i) => [i.product_id, i.qty]));
    try {
      setResult(
        await judgeApi.challenge(
          profile,
          items,
          {
            budget: budget ? Number(budget) : null,
            sites: sites ? Number(sites) : null,
            city_tier: tier ? (Number(tier) as 1 | 2) : null,
            gstin_active: noGst ? false : null,
            connection: connection || null,
            add: add ? [add] : [],
            remove: removed,
            must_have: essential,
          },
          employees ? Number(employees) : null,
        ),
      );
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const current = plan?.tiers[tierIdx];
  const toggle = (list: string[], set: (v: string[]) => void, id: string) =>
    set(list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);
  const scenario = scenarios.find((s) => s.id === scenarioId);

  return (
    <div className="min-h-dvh bg-paper text-ink">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 md:px-8">
        <Link href="/" className="flex min-h-11 items-center gap-2 font-semibold">
          <Image src="/icon.svg" alt="" width={28} height={28} className="size-7" />
          Udyam Digital
        </Link>
        <Link href="/" className="min-h-11 content-center text-sm text-ink-soft hover:text-ink">
          Back to the overview
        </Link>
      </header>

      <main className="mx-auto max-w-6xl px-4 pb-16 md:px-8">
        <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">Judge challenge</h1>
        <p className="mt-3 max-w-[70ch] text-ink-soft">
          Pick a business, then break its quote: cut the budget, add a service, grow the sites, move city, lose GST, or force a
          different connection. The system explains what broke and which rule broke it, and offers the smallest valid fix
          or a clear trade-off. Every option is re-checked by the rules engine before you see it.
        </p>

        <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,22rem)_1fr]">
          {/* Controls */}
          <section aria-label="Scenario and changes" className="flex flex-col gap-5">
            <div>
              <h2 className="font-semibold">1. Pick a business</h2>
              <div className="mt-2 flex flex-col gap-1.5">
                {scenarios.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    aria-pressed={scenarioId === s.id}
                    onClick={() => pickScenario(s.id)}
                    className="min-h-11 cursor-pointer rounded-bill border border-line bg-surface px-3 text-left text-sm hover:border-pen aria-pressed:border-pen aria-pressed:font-medium"
                  >
                    {s.label}
                  </button>
                ))}
              </div>
              <details className="mt-3 rounded-bill border border-line bg-surface p-3 text-sm">
                <summary className="cursor-pointer font-medium">Or build your own</summary>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <label className="col-span-2 flex flex-col gap-1">
                    Segment
                    <select
                      value={profile.segment}
                      onChange={(e) => setProfile({ ...profile, segment: e.target.value as JudgeProfile["segment"] })}
                      className="min-h-10 rounded-bill border border-line bg-paper px-2"
                    >
                      {SEGMENTS.map(([v, l]) => (
                        <option key={v} value={v}>
                          {l}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="flex flex-col gap-1">
                    Employees
                    <input
                      type="number"
                      min={1}
                      value={profile.employees}
                      onChange={(e) => setProfile({ ...profile, employees: Math.max(1, Number(e.target.value)) })}
                      className="min-h-10 rounded-bill border border-line bg-paper px-2"
                    />
                  </label>
                  <label className="flex flex-col gap-1">
                    Sites
                    <input
                      type="number"
                      min={1}
                      value={profile.sites}
                      onChange={(e) => setProfile({ ...profile, sites: Math.max(1, Number(e.target.value)) })}
                      className="min-h-10 rounded-bill border border-line bg-paper px-2"
                    />
                  </label>
                  <label className="flex flex-col gap-1">
                    City tier
                    <select
                      value={profile.city_tier}
                      onChange={(e) => setProfile({ ...profile, city_tier: Number(e.target.value) as 1 | 2 })}
                      className="min-h-10 rounded-bill border border-line bg-paper px-2"
                    >
                      <option value={1}>Tier 1</option>
                      <option value={2}>Tier 2</option>
                    </select>
                  </label>
                  <label className="flex min-h-10 items-center gap-2 self-end">
                    <input
                      type="checkbox"
                      checked={profile.gstin_active}
                      onChange={(e) => setProfile({ ...profile, gstin_active: e.target.checked })}
                      className="size-5 accent-[rgb(var(--pen))]"
                    />
                    Active GST
                  </label>
                </div>
                <Button
                  variant="quiet"
                  className="mt-3 min-h-10 text-sm"
                  onClick={() => {
                    setScenarioId("");
                    void build(profile);
                  }}
                >
                  Build plans
                </Button>
              </details>
            </div>

            {plan && current && (
              <>
                <div>
                  <h2 className="font-semibold">2. Its quote</h2>
                  <div role="radiogroup" aria-label="Plan" className="mt-2 grid grid-flow-col gap-1 rounded-bill bg-line/60 p-1">
                    {plan.tiers.map((t, i) => (
                      <button
                        key={t.tier}
                        role="radio"
                        aria-checked={i === tierIdx}
                        onClick={() => {
                          setTierIdx(i);
                          setEssential([]);
                          setRemoved([]);
                          setResult(null);
                        }}
                        className={cn(
                          "min-h-10 cursor-pointer rounded-[4px] text-sm",
                          i === tierIdx ? "bg-surface font-medium shadow-sm" : "text-ink-soft",
                        )}
                      >
                        {TIER_LABEL[t.tier] ?? t.tier}
                      </button>
                    ))}
                  </div>
                  <ul className="mt-2 divide-y divide-line rounded-bill border border-line bg-surface text-sm">
                    {current.items.map((i) => (
                      <li key={i.product_id} className="flex items-center gap-2 p-2">
                        <span className={cn("flex-1", removed.includes(i.product_id) && "text-ink-soft line-through")}>
                          {i.name} × {i.qty}
                        </span>
                        <label className="flex items-center gap-1 text-xs text-ink-soft">
                          <input
                            type="checkbox"
                            checked={essential.includes(i.product_id)}
                            onChange={() => toggle(essential, setEssential, i.product_id)}
                            className="size-4 accent-[rgb(var(--pen))]"
                          />
                          essential
                        </label>
                        <button
                          type="button"
                          onClick={() => toggle(removed, setRemoved, i.product_id)}
                          className="min-h-9 cursor-pointer rounded px-2 text-xs text-pen hover:underline"
                        >
                          {removed.includes(i.product_id) ? "keep" : "remove"}
                        </button>
                      </li>
                    ))}
                    <li className="money flex justify-between p-2 font-semibold">
                      <span>Monthly</span>
                      <span>{formatINR(current.monthly_total)}</span>
                    </li>
                  </ul>
                </div>

                <div>
                  <h2 className="font-semibold">3. Break it</h2>
                  {scenario && <p className="mt-1 text-sm text-ink-soft">Try: {scenario.try}</p>}
                  <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
                    <label className="col-span-2 flex flex-col gap-1">
                      Budget (₹ per month)
                      <input
                        inputMode="numeric"
                        value={budget}
                        onChange={(e) => setBudget(e.target.value.replace(/\D/g, ""))}
                        className="money min-h-10 rounded-bill border border-line bg-surface px-2"
                      />
                    </label>
                    <label className="col-span-2 flex flex-col gap-1">
                      Add a service
                      <select value={add} onChange={(e) => setAdd(e.target.value)} className="min-h-10 rounded-bill border border-line bg-surface px-2">
                        <option value="">None</option>
                        {plan.rules
                          .filter((r) => !current.items.some((i) => i.product_id === r.product_id))
                          .map((r) => (
                            <option key={r.product_id} value={r.product_id}>
                              {r.name}
                              {r.eligible ? "" : " (not eligible now)"}
                            </option>
                          ))}
                      </select>
                    </label>
                    <label className="flex flex-col gap-1">
                      Sites
                      <input inputMode="numeric" value={sites} onChange={(e) => setSites(e.target.value.replace(/\D/g, ""))} className="money min-h-10 rounded-bill border border-line bg-surface px-2" />
                    </label>
                    <label className="flex flex-col gap-1">
                      Employees
                      <input inputMode="numeric" value={employees} onChange={(e) => setEmployees(e.target.value.replace(/\D/g, ""))} className="money min-h-10 rounded-bill border border-line bg-surface px-2" />
                    </label>
                    <label className="flex flex-col gap-1">
                      City tier
                      <select value={tier} onChange={(e) => setTier(e.target.value)} className="min-h-10 rounded-bill border border-line bg-surface px-2">
                        <option value="">Keep</option>
                        <option value="1">Tier 1</option>
                        <option value="2">Tier 2</option>
                      </select>
                    </label>
                    <label className="flex flex-col gap-1">
                      Connection
                      <select value={connection} onChange={(e) => setConnection(e.target.value)} className="min-h-10 rounded-bill border border-line bg-surface px-2">
                        <option value="">Keep</option>
                        {PRIMARY_CONNECTIONS.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    {profile.gstin_active && (
                      <label className="col-span-2 flex min-h-10 items-center gap-2">
                        <input type="checkbox" checked={noGst} onChange={(e) => setNoGst(e.target.checked)} className="size-5 accent-[rgb(var(--pen))]" />
                        GST registration lapses
                      </label>
                    )}
                  </div>
                  <Button width="full" className="mt-3" disabled={busy} onClick={run}>
                    {busy ? "Checking…" : "Run the rules"}
                  </Button>
                </div>
              </>
            )}
            {error && (
              <p role="alert" className="text-sm text-alert">
                {error}
              </p>
            )}
          </section>

          {/* Results */}
          <section
            ref={decisionRef}
            aria-label="Decision"
            className="min-w-0 scroll-mt-4 lg:sticky lg:top-4 lg:max-h-[calc(100dvh-2rem)] lg:self-start lg:overflow-y-auto lg:pr-1"
          >
            {!plan && (
              <p className="rounded-bill border border-dashed border-line p-6 text-ink-soft">
                Pick a business on the left to load its quote.
              </p>
            )}
            {plan && !result && (
              <p className="rounded-bill border border-dashed border-line p-6 text-ink-soft">
                Change something under “Break it” and run the rules. The decision, the rule behind each change and the
                independent re-check appear here.
              </p>
            )}
            {result && current && (
              <>
                <h2 className="mb-3 font-semibold">The system&apos;s decision</h2>
                <RepairOptions
                  result={result}
                  currentTotal={result.before_total}
                  budget={budget ? Number(budget) : null}
                  audit={result.audit}
                />
              </>
            )}
            {(result?.rules_after ?? plan?.rules) && (
              <div className="mt-6">
                <button type="button" onClick={() => setShowRules((v) => !v)} className="min-h-11 cursor-pointer text-sm font-medium text-pen hover:underline">
                  {showRules ? "Hide" : "Show"} all 25 products and the rule each one hits{result ? " after the change" : ""}
                </button>
                {showRules && (
                  <div className="mt-2 overflow-x-auto rounded-bill border border-line bg-surface">
                    <table className="w-full min-w-[560px] text-sm">
                      <thead>
                        <tr className="text-left text-ink-soft">
                          <th className="px-3 py-2 font-medium">Product</th>
                          <th className="px-3 py-2 font-medium">Allowed?</th>
                          <th className="px-3 py-2 font-medium">Why not</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(result?.rules_after ?? plan!.rules).map((r) => (
                          <tr key={r.product_id} className="border-t border-line">
                            <td className="px-3 py-1.5">{r.name}</td>
                            <td className="px-3 py-1.5">
                              {r.eligible ? (
                                <span className="flex items-center gap-1 text-stamp">
                                  <CheckCircle2 aria-hidden className="size-4" /> yes
                                </span>
                              ) : (
                                <span className="flex items-center gap-1 text-alert">
                                  <XCircle aria-hidden className="size-4" /> no
                                </span>
                              )}
                            </td>
                            <td className="px-3 py-1.5 text-ink-soft">
                              {r.reasons.join("; ")}
                              {r.rules.map((rule) => (
                                <RuleBadge key={rule} rule={rule} />
                              ))}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </section>
        </div>

        {/* Scorecard */}
        {score?.available && (
          <section className="mt-16 border-t border-line pt-10" aria-label="Test results">
            <h2 className="text-2xl font-semibold tracking-tight">Prototype test results</h2>
            <p className="mt-1 text-sm text-ink-soft">
              Measured on the case data by <code>scripts/scorecard.py</code>
              {score.generated_at && `, ${new Date(score.generated_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}`}.
              Separate from any projected business impact.
            </p>
            <dl className="mt-6 grid gap-px overflow-hidden rounded-bill border border-line bg-line sm:grid-cols-2 lg:grid-cols-4">
              <div className="bg-surface p-4">
                <dt className="text-sm text-ink-soft">Ineligible plans, all 5,000 leads</dt>
                <dd className="money mt-1 text-2xl font-semibold">{score.lead_sweep?.ineligible_plans}</dd>
                <dd className="text-xs text-ink-soft">of {fmt.format(score.lead_sweep?.plans_checked ?? 0)} plans checked</dd>
              </div>
              <div className="bg-surface p-4">
                <dt className="text-sm text-ink-soft">Advisor personas passed</dt>
                <dd className="money mt-1 text-2xl font-semibold">
                  {score.personas?.passed}/{score.personas?.total}
                </dd>
                <dd className="text-xs text-ink-soft">at most {score.personas?.max_turns} turns each</dd>
              </div>
              <div className="bg-surface p-4">
                <dt className="text-sm text-ink-soft">Quote repair: valid fix found</dt>
                <dd className="money mt-1 text-2xl font-semibold">
                  {score.repair?.valid_fix_found}/{score.repair?.solvable_within_budget}
                </dd>
                <dd className="text-xs text-ink-soft">
                  solvable cases; {score.repair?.invalid_options} invalid options in {fmt.format(score.repair?.cases ?? 0)} random changes
                </dd>
              </div>
              <div className="bg-surface p-4">
                <dt className="text-sm text-ink-soft">KYC answer key</dt>
                <dd className="money mt-1 text-2xl font-semibold">
                  {score.kyc?.correct}/{score.kyc?.total}
                </dd>
                <dd className="text-xs text-ink-soft">specimen applicants judged correctly</dd>
              </div>
            </dl>
            {score.kyc && (
              <div className="mt-6 overflow-x-auto rounded-bill border border-line bg-surface">
                <table className="w-full min-w-[640px] text-sm">
                  <caption className="sr-only">KYC answer key results</caption>
                  <thead>
                    <tr className="text-left text-ink-soft">
                      <th className="px-3 py-2 font-medium">Applicant</th>
                      <th className="px-3 py-2 font-medium">Planted finding</th>
                      <th className="px-3 py-2 font-medium">Expected</th>
                      <th className="px-3 py-2 font-medium">System</th>
                      <th className="px-3 py-2 font-medium">Reason given</th>
                    </tr>
                  </thead>
                  <tbody>
                    {score.kyc.applicants.map((a) => (
                      <tr key={a.applicant} className="border-t border-line align-top">
                        <td className="px-3 py-2 font-medium">{a.applicant}</td>
                        <td className="px-3 py-2">{a.finding}</td>
                        <td className="px-3 py-2">{a.expected}</td>
                        <td className={cn("px-3 py-2 font-medium", a.ok ? "text-stamp" : "text-alert")}>{a.actual}</td>
                        <td className="px-3 py-2 text-ink-soft">{a.reason || "–"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  );
}
