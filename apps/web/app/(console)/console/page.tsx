"use client";

import { useEffect, useState } from "react";

import { HBar } from "@/components/console/hbar";
import { consoleApi, type Funnel } from "@/lib/console";

const fmt = new Intl.NumberFormat("en-IN");
const inr = (v: number) => `₹${fmt.format(Math.round(v))}`;
const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

export default function ConsoleHome() {
  const [data, setData] = useState<Funnel | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [table, setTable] = useState(false);

  useEffect(() => {
    consoleApi.funnel().then(setData).catch((e) => setError(String(e.message ?? e)));
  }, []);

  if (error) return <p role="alert" className="text-alert">{error}</p>;
  if (!data) return <p className="animate-pulse text-ink-soft">Loading funnel…</p>;

  const h = data.history;
  const stages = h.stages.map((s, i) => ({
    ...s,
    step: i === 0 ? null : s.count / h.stages[i - 1].count,
  }));
  const kpis = [
    { label: "Lead to activation", value: pct(h.conversion) },
    { label: "Days from lead to working", value: h.avg_days_to_activate.toFixed(1) },
    { label: "Cost per activated customer", value: inr(h.cac) },
    { label: "Times customers chased us", value: h.avg_follow_up_calls.toFixed(1) },
  ];
  const sources = [...h.by_source].sort((a, b) => b.conversion - a.conversion);

  return (
    <div className="flex max-w-5xl flex-col gap-8">
      <header>
        <h1 className="text-2xl font-semibold">Funnel</h1>
        <p className="text-sm text-ink-soft">Field and partner leads, April to June 2026 (5,000 leads), against the digital journey.</p>
      </header>

      <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-bill border border-line bg-line md:grid-cols-4">
        {kpis.map((k) => (
          <div key={k.label} className="bg-surface p-4">
            <dt className="text-sm text-ink-soft">{k.label}</dt>
            <dd className="money mt-1 text-2xl font-semibold">{k.value}</dd>
          </div>
        ))}
      </dl>

      <section className="rounded-bill border border-line bg-surface p-4">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="font-semibold">Leads reaching each stage</h2>
          <button type="button" onClick={() => setTable((v) => !v)} className="min-h-11 cursor-pointer text-sm text-pen hover:underline">
            {table ? "Show chart" : "Show table"}
          </button>
        </div>
        {table ? (
          <table className="mt-3 w-full text-sm">
            <thead>
              <tr className="text-left text-ink-soft">
                <th className="pb-2 font-medium">Stage</th>
                <th className="pb-2 text-right font-medium">Leads</th>
                <th className="pb-2 text-right font-medium">From previous stage</th>
              </tr>
            </thead>
            <tbody>
              {stages.map((s) => (
                <tr key={s.stage} className="border-t border-line">
                  <td className="py-2">{s.stage}</td>
                  <td className="money py-2 text-right">{fmt.format(s.count)}</td>
                  <td className="money py-2 text-right text-ink-soft">{s.step === null ? "" : pct(s.step)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <HBar
            label="Leads reaching each stage"
            data={stages}
            category="stage"
            value="count"
            format={(v) => fmt.format(v)}
            tooltip={(r) => `${fmt.format(r.count)} leads${r.step === null ? "" : `, ${pct(r.step)} of previous stage`}`}
          />
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-bill border border-line bg-surface p-4">
          <h2 className="font-semibold">Conversion by lead source</h2>
          <HBar label="Conversion by lead source" data={sources} category="source" value="conversion" format={pct} tooltip={(r) => `${pct(r.conversion)} of ${fmt.format(r.leads)} leads`} />
        </section>
        <section className="rounded-bill border border-line bg-surface p-4">
          <h2 className="font-semibold">Cost per activated customer, by source</h2>
          <HBar label="Cost per activated customer by source" data={[...h.by_source].sort((a, b) => a.cac - b.cac)} category="source" value="cac" format={inr} />
        </section>
      </div>

      <section className="rounded-bill border border-line bg-surface p-4">
        <h2 className="font-semibold">Why leads dropped</h2>
        <HBar label="Top drop reasons" data={h.drop_reasons} category="reason" value="count" format={(v) => fmt.format(v)} />
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-bill border border-line bg-surface p-4">
          <h2 className="font-semibold">Digital journey (live)</h2>
          <table className="mt-3 w-full text-sm">
            <tbody>
              {data.live.stages.map((s) => (
                <tr key={s.stage} className="border-t border-line first:border-t-0">
                  <td className="py-2">{s.stage}</td>
                  <td className="money py-2 text-right">{fmt.format(s.count)}</td>
                </tr>
              ))}
              <tr className="border-t border-line">
                <td className="py-2">Orders placed</td>
                <td className="money py-2 text-right">{data.live.orders}</td>
              </tr>
              <tr className="border-t border-line">
                <td className="py-2">Waiting for a call</td>
                <td className="money py-2 text-right">{data.live.needs_human}</td>
              </tr>
            </tbody>
          </table>
        </section>
        <section className="rounded-bill border border-line bg-surface p-4">
          <h2 className="font-semibold">Partner credit for digital orders</h2>
          <table className="mt-3 w-full text-sm">
            <thead>
              <tr className="text-left text-ink-soft">
                <th className="pb-2 font-medium">Team</th>
                <th className="pb-2 font-medium">Territory</th>
                <th className="pb-2 text-right font-medium">Orders</th>
              </tr>
            </thead>
            <tbody>
              {data.credits.map((c) => (
                <tr key={c.username} className="border-t border-line">
                  <td className="py-2">{c.name}</td>
                  <td className="py-2 text-ink-soft">{c.city}</td>
                  <td className="money py-2 text-right">{c.digital_orders}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
}
