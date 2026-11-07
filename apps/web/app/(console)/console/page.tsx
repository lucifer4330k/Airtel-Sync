// Funnel from the case README (Apr–Jun 2026, 5,000 leads). Replaced by
// GET /console/funnel once leads are served from Postgres.
const FUNNEL = [
  { stage: "Lead", count: 5000 },
  { stage: "Contacted", count: 3406 },
  { stage: "Needs assessed", count: 1974 },
  { stage: "Quote accepted", count: 861 },
  { stage: "KYC complete", count: 588 },
  { stage: "Activated", count: 368 },
];

const KPIS = [
  { label: "Lead to activation", value: "7.4%" },
  { label: "Average days to activate", value: "17.6" },
  { label: "Acquisition cost per customer", value: "₹15,000" },
  { label: "Follow-up calls per customer", value: "3" },
];

const fmt = new Intl.NumberFormat("en-IN");

export default function ConsoleHome() {
  const top = FUNNEL[0].count;
  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-semibold">Funnel, April to June 2026</h1>

      <dl className="mt-6 grid grid-cols-2 gap-px overflow-hidden rounded-bill border border-line bg-line md:grid-cols-4">
        {KPIS.map((k) => (
          <div key={k.label} className="bg-surface p-4">
            <dt className="text-sm text-ink-soft">{k.label}</dt>
            <dd className="money mt-1 text-2xl font-semibold">{k.value}</dd>
          </div>
        ))}
      </dl>

      <table className="mt-8 w-full text-sm">
        <caption className="sr-only">Leads reaching each stage</caption>
        <thead>
          <tr className="text-left text-ink-soft">
            <th className="pb-2 font-medium">Stage</th>
            <th className="pb-2 text-right font-medium">Leads</th>
            <th className="pb-2 text-right font-medium">From previous</th>
            <th className="w-2/5 pb-2 pl-4 font-medium">
              <span className="sr-only">Share of all leads</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {FUNNEL.map((row, i) => (
            <tr key={row.stage} className="border-t border-line">
              <td className="py-2.5">{row.stage}</td>
              <td className="money py-2.5 text-right">{fmt.format(row.count)}</td>
              <td className="money py-2.5 text-right text-ink-soft">
                {i === 0 ? "" : `${Math.round((row.count / FUNNEL[i - 1].count) * 100)}%`}
              </td>
              <td className="py-2.5 pl-4">
                <div className="h-2 rounded-full bg-pen" style={{ width: `${(row.count / top) * 100}%` }} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
