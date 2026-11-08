"use client";

import { ArrowDown, ArrowUp, PhoneCall, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { consoleApi, consoleSession, type ConsoleUser, type LeadDetail, type LeadRow, type Reason } from "@/lib/console";
import { cn, formatINR } from "@/lib/utils";

const VIEWS = [
  { key: "needs_human", label: "Waiting for a call" },
  { key: "open", label: "Open" },
  { key: "digital", label: "Digital journeys" },
  { key: "all", label: "All" },
] as const;
const STOPPED = { advisor: "In the advisor", quote: "At the quote", kyc: "At documents", install: "Awaiting install" } as const;

function Score({ value }: { value: number | null }) {
  if (value === null) return <span className="text-ink-soft">–</span>;
  return (
    <span className="flex items-center gap-2">
      <span className="h-1.5 w-14 overflow-hidden rounded-full bg-line" aria-hidden>
        <span className="block h-full rounded-full bg-chart" style={{ width: `${Math.min(100, value * 400)}%` }} />
      </span>
      <span className="money text-sm">{(value * 100).toFixed(1)}%</span>
    </span>
  );
}

function Reasons({ reasons }: { reasons: Reason[] }) {
  return (
    <ul className="flex flex-col gap-0.5 text-xs">
      {reasons.map((r) => (
        <li key={r.feature} className="flex items-center gap-1 text-ink-soft">
          {r.effect === "up" ? (
            <ArrowUp aria-label="raises the score" className="size-3 text-stamp" />
          ) : (
            <ArrowDown aria-label="lowers the score" className="size-3 text-alert" />
          )}
          {r.label}
        </li>
      ))}
    </ul>
  );
}

export default function LeadsPage() {
  const [view, setView] = useState<(typeof VIEWS)[number]["key"]>("needs_human");
  const [q, setQ] = useState("");
  const [minScore, setMinScore] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<{ total: number; items: LeadRow[] } | null>(null);
  const [selected, setSelected] = useState<LeadDetail | null>(null);
  const [team, setTeam] = useState<ConsoleUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const me = consoleSession.get()?.user;

  const load = useCallback(async () => {
    setError(null);
    try {
      setData(await consoleApi.leads({ view, q: q || undefined, min_score: minScore || undefined, page, size: 25 }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }, [view, q, minScore, page]);

  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    consoleApi.team().then(setTeam).catch(() => undefined);
  }, []);

  async function open(id: number) {
    setSelected(await consoleApi.lead(id));
  }

  return (
    <div className="flex flex-col gap-4 xl:flex-row">
      <div className="min-w-0 flex-1">
        <h1 className="text-2xl font-semibold">Leads</h1>
        <div className="mt-3 flex flex-wrap items-end gap-2">
          <div role="tablist" aria-label="Lead view" className="flex rounded-bill bg-line/60 p-1">
            {VIEWS.map((v) => (
              <button
                key={v.key}
                role="tab"
                aria-selected={view === v.key}
                onClick={() => {
                  setView(v.key);
                  setPage(1);
                }}
                className={cn(
                  "min-h-10 cursor-pointer rounded-[4px] px-3 text-sm",
                  view === v.key ? "bg-surface font-medium shadow-sm" : "text-ink-soft hover:text-ink",
                )}
              >
                {v.label}
              </button>
            ))}
          </div>
          <label className="flex flex-col text-xs text-ink-soft">
            Search
            <input
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setPage(1);
              }}
              placeholder="Name, type or L00042"
              className="min-h-10 rounded-bill border border-line bg-surface px-3 text-sm text-ink"
            />
          </label>
          <label className="flex flex-col text-xs text-ink-soft">
            Likelihood
            <select
              value={minScore}
              onChange={(e) => {
                setMinScore(e.target.value);
                setPage(1);
              }}
              className="min-h-10 cursor-pointer rounded-bill border border-line bg-surface px-2 text-sm text-ink"
            >
              <option value="">Any</option>
              <option value="0.1">10% and above</option>
              <option value="0.15">15% and above</option>
              <option value="0.2">20% and above</option>
            </select>
          </label>
        </div>

        {error && <p role="alert" className="mt-3 text-sm text-alert">{error}</p>}
        {data && (
          <>
            <p className="mt-3 text-sm text-ink-soft">{data.total.toLocaleString("en-IN")} leads, likeliest to close first</p>
            <div className="mt-2 overflow-x-auto rounded-bill border border-line bg-surface">
              <table className="w-full min-w-[720px] text-sm">
                <thead>
                  <tr className="text-left text-ink-soft">
                    <th className="px-3 py-2 font-medium">Business</th>
                    <th className="px-3 py-2 font-medium">Where it stopped</th>
                    <th className="px-3 py-2 font-medium">Likelihood to activate</th>
                    <th className="px-3 py-2 font-medium">Why</th>
                    <th className="px-3 py-2 font-medium">Owner</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((l) => (
                    <tr
                      key={l.id}
                      onClick={() => open(l.id)}
                      className={cn(
                        "cursor-pointer border-t border-line align-top hover:bg-paper",
                        selected?.id === l.id && "bg-paper",
                      )}
                    >
                      <td className="px-3 py-2">
                        <button type="button" className="text-left font-medium hover:underline" onClick={() => open(l.id)}>
                          {l.business}
                        </button>
                        <p className="text-xs text-ink-soft">
                          {l.type} · {l.city} · {l.employees} staff{l.sites > 1 ? `, ${l.sites} sites` : ""}
                        </p>
                      </td>
                      <td className="px-3 py-2">
                        {l.needs_human && (
                          <span className="mb-1 flex items-center gap-1 text-xs font-medium text-marigold">
                            <PhoneCall aria-hidden className="size-3" />
                            Call requested
                          </span>
                        )}
                        <p>{l.stopped_at ? STOPPED[l.stopped_at as keyof typeof STOPPED] ?? l.stopped_at : l.stage}</p>
                        <p className="text-xs text-ink-soft">{l.needs_human_reason ?? l.drop_reason ?? l.source}</p>
                      </td>
                      <td className="px-3 py-2">
                        <Score value={l.score} />
                      </td>
                      <td className="px-3 py-2">
                        <Reasons reasons={l.reasons} />
                      </td>
                      <td className="px-3 py-2 text-ink-soft">{l.assigned_to ?? "Unassigned"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-3 flex gap-2">
              <Button variant="quiet" disabled={page === 1} onClick={() => setPage((p) => p - 1)} className="min-h-10 text-sm">
                Previous
              </Button>
              <Button variant="quiet" disabled={page * 25 >= data.total} onClick={() => setPage((p) => p + 1)} className="min-h-10 text-sm">
                Next
              </Button>
            </div>
          </>
        )}
      </div>

      {selected && (
        <LeadPanel
          lead={selected}
          team={team}
          me={me}
          onClose={() => setSelected(null)}
          onChanged={async () => {
            await open(selected.id);
            await load();
          }}
        />
      )}
    </div>
  );
}

function LeadPanel({
  lead,
  team,
  me,
  onClose,
  onChanged,
}: {
  lead: LeadDetail;
  team: ConsoleUser[];
  me?: ConsoleUser;
  onClose: () => void;
  onChanged: () => Promise<void>;
}) {
  const [note, setNote] = useState("");
  const [outcome, setOutcome] = useState("");
  const [assignee, setAssignee] = useState("");
  const [error, setError] = useState<string | null>(null);
  const candidates = team.filter((u) => u.role !== "admin" && (!u.city || u.city === lead.city));

  async function act(fn: () => Promise<unknown>) {
    setError(null);
    try {
      await fn();
      await onChanged();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  return (
    <aside aria-label={`Lead ${lead.business}`} className="w-full shrink-0 rounded-bill border border-line bg-surface p-4 xl:sticky xl:top-6 xl:max-h-[calc(100dvh-3rem)] xl:w-[26rem] xl:overflow-y-auto">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold">{lead.business}</h2>
          <p className="text-sm text-ink-soft">
            {lead.external_id ?? "Digital"} · {lead.segment} · {lead.city}
          </p>
        </div>
        <button type="button" onClick={onClose} aria-label="Close" className="flex size-11 cursor-pointer items-center justify-center rounded-bill hover:bg-paper">
          <X aria-hidden className="size-4" />
        </button>
      </div>

      <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
        <div>
          <dt className="text-ink-soft">Phone</dt>
          <dd className="money">{lead.phone ?? "–"}</dd>
        </div>
        <div>
          <dt className="text-ink-soft">GSTIN</dt>
          <dd className="money">{lead.gstin ?? "–"}</dd>
        </div>
        <div>
          <dt className="text-ink-soft">Current internet</dt>
          <dd>{lead.current_internet ?? "–"}</dd>
        </div>
        <div>
          <dt className="text-ink-soft">Telecom spend</dt>
          <dd className="money">{lead.telecom_spend ? `${formatINR(lead.telecom_spend)}/mo` : "–"}</dd>
        </div>
      </dl>

      <section className="mt-4">
        <h3 className="text-sm font-semibold">Likelihood to activate</h3>
        <div className="mt-1">
          <Score value={lead.score} />
        </div>
        <div className="mt-2">
          <Reasons reasons={lead.reasons} />
        </div>
      </section>

      {lead.needs_human_reason && (
        <p className="mt-4 rounded-bill border border-marigold/50 p-2 text-sm">{lead.needs_human_reason}</p>
      )}

      {lead.quotes.length > 0 && (
        <section className="mt-4">
          <h3 className="text-sm font-semibold">Plans offered</h3>
          <ul className="mt-1 text-sm">
            {lead.quotes.map((q) => (
              <li key={q.id} className="flex justify-between">
                <span className="capitalize">
                  {q.tier} <span className="text-ink-soft">({q.status})</span>
                </span>
                <span className="money">{formatINR(q.monthly_total)}/mo</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {lead.kyc && (
        <p className="mt-3 text-sm">
          KYC: <strong>{lead.kyc.overall}</strong>
          {lead.kyc.reasons[0] && <span className="block text-ink-soft">{lead.kyc.reasons[0]}</span>}
        </p>
      )}

      <section className="mt-4 flex flex-col gap-2">
        <h3 className="text-sm font-semibold">Assign</h3>
        <p className="text-sm text-ink-soft">Now: {lead.assigned_to ?? "unassigned"}</p>
        <div className="flex gap-2">
          <select
            aria-label="Assign to"
            value={assignee}
            onChange={(e) => setAssignee(e.target.value)}
            className="min-h-10 flex-1 cursor-pointer rounded-bill border border-line bg-paper px-2 text-sm"
          >
            <option value="">{me?.role === "admin" ? "Choose rep or partner" : "Take this lead"}</option>
            {(me?.role === "admin" ? candidates : team.filter((u) => u.username === me?.username)).map((u) => (
              <option key={u.username} value={u.username}>
                {u.name}
              </option>
            ))}
          </select>
          <Button variant="quiet" className="min-h-10 text-sm" disabled={!assignee} onClick={() => act(() => consoleApi.assign(lead.id, assignee))}>
            Assign
          </Button>
        </div>
      </section>

      <section className="mt-4 flex flex-col gap-2">
        <h3 className="text-sm font-semibold">Follow-up</h3>
        <textarea
          aria-label="Follow-up note"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={2}
          placeholder="What happened?"
          className="rounded-bill border border-line bg-paper p-2 text-sm"
        />
        <div className="flex gap-2">
          <select
            aria-label="Outcome"
            value={outcome}
            onChange={(e) => setOutcome(e.target.value)}
            className="min-h-10 flex-1 cursor-pointer rounded-bill border border-line bg-paper px-2 text-sm"
          >
            <option value="">No outcome yet</option>
            <option value="called">Called</option>
            <option value="visit_booked">Visit booked</option>
            <option value="not_reachable">Not reachable</option>
            <option value="not_interested">Not interested</option>
          </select>
          <Button
            variant="quiet"
            className="min-h-10 text-sm"
            disabled={note.trim().length < 2}
            onClick={() =>
              act(async () => {
                await consoleApi.followUp(lead.id, note.trim(), outcome);
                setNote("");
                setOutcome("");
              })
            }
          >
            Save
          </Button>
        </div>
        {lead.follow_ups.length > 0 && (
          <ol className="mt-1 flex flex-col gap-1 text-xs text-ink-soft">
            {[...lead.follow_ups].reverse().map((f, i) => (
              <li key={i}>
                <span className="text-ink">{f.note}</span> · {f.by} · {new Date(f.at).toLocaleDateString("en-IN")}
              </li>
            ))}
          </ol>
        )}
      </section>

      {error && <p role="alert" className="mt-3 text-sm text-alert">{error}</p>}

      {lead.transcript.length > 0 && (
        <section className="mt-4">
          <h3 className="text-sm font-semibold">Advisor conversation</h3>
          <ol className="mt-2 flex flex-col gap-2 text-sm">
            {lead.transcript.map((m, i) => (
              <li key={i} className={cn("whitespace-pre-line rounded-bill p-2", m.role === "owner" ? "bg-paper" : "border border-line")}>
                <span className="block text-xs text-ink-soft">{m.role === "owner" ? "Owner" : "Advisor"}</span>
                {m.text}
              </li>
            ))}
          </ol>
        </section>
      )}
    </aside>
  );
}
