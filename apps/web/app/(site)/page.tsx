import { ArrowUpRight, Check, CheckCheck, Download, Minus, Plus, X } from "lucide-react";
import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

import { ApiStatus } from "@/components/site/api-status";
import { ExplodedPhone } from "@/components/site/exploded-phone";
import { Funnel3D, PROCESS_LOST } from "@/components/site/funnel-3d";
import s from "@/components/site/landing.module.css";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Udyam Digital: connect a small business from one phone",
  description:
    "AI advisor, one monthly price, quote repair, Smart KYC and WhatsApp order tracking for India's small businesses, with a partner console for the leads that need a person.",
};

/*
 * Page order follows the argument: what goes wrong today (the case's own funnel),
 * what replaces each broken step, how each piece works, how it was tested, then
 * how to try it. Display type is Bricolage Grotesque; everything else stays on
 * the app's IBM Plex so the page and the product read as one thing.
 */

const REPO = process.env.NEXT_PUBLIC_REPO_URL;
const API_DOCS = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1").replace(/\/api\/v1$/, "/docs");

const ctaPrimary =
  "inline-flex min-h-12 items-center justify-center gap-2 rounded-bill bg-marigold px-5 font-semibold text-night transition-colors hover:bg-[rgb(240_188_72)]";
const ctaGhost =
  "inline-flex min-h-12 items-center justify-center gap-2 rounded-bill border border-white/30 px-5 font-semibold text-white transition-colors hover:bg-white/10";

// The journey as a bill: each line is what the owner now does, and the old step
// it replaces with the businesses lost to it (smb_leads.csv drop reasons).
// The lost counts add up to PROCESS_LOST.
const BILL = [
  {
    now: "Describe the business in your own words",
    how: "Typed or spoken, in English, Hindi or Hinglish. At most six questions; the GSTIN is checked against the registry while you type.",
    was: "Wait for a sales visit",
    lost: 827,
    why: "no time for a visit, or it was never scheduled",
  },
  {
    now: "See one monthly price, and change it",
    how: "Essential, Recommended or Complete. Change the budget or the needs and the plan is repaired on the spot.",
    was: "Wait days for a quote",
    lost: 385,
    why: "quote too slow or too complex",
  },
  {
    now: "Approve UPI AutoPay",
    how: "The order is placed, the activation date set from install times, and the first WhatsApp update sent.",
    was: "Pay after the visit",
    lost: 28,
    why: "first payment failed",
  },
  {
    now: "Photograph four documents",
    how: "Read, checked against the registries and against each other, and explained in plain words if something is wrong.",
    was: "Hand over paperwork in person",
    lost: 273,
    why: "missing, mismatched or too much paperwork",
  },
  {
    now: "Follow the install on WhatsApp",
    how: "A message at every step, an expected date from day one, and the engineer visit can be moved from the link.",
    was: "Call to ask where the order is",
    lost: 98,
    why: "install slipped past 21 days",
  },
];

const PROOF = [
  ["0 of 14,937", "plans built for all 5,000 leads contained a product the business can't have"],
  ["27 of 27", "advisor personas got the plan they should, in five turns or fewer"],
  ["564 of 564", "randomly broken quotes that could fit the budget were repaired, with 0 invalid options in 1,000"],
  ["12 of 12", "KYC applicants given the right verdict and reason, from 47 document images"],
  ["0.67", "ROC-AUC of the lead score, using only what is known when the lead arrives"],
] as const;

const SAMPLES = [
  ["clean-gst_certificate.png", "GST certificate", "passes"],
  ["clean-udyam_certificate.png", "Udyam certificate", "passes"],
  ["clean-signatory_id.png", "Signatory ID", "passes"],
  ["clean-address_proof.png", "Address proof", "passes"],
  ["old-address-proof.png", "Address proof, 257 days old", "fails"],
  ["blurred-gst-certificate.png", "Blurred GST certificate", "fails"],
] as const;

function Fragment({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        "rounded-xl bg-surface p-5 text-sm shadow-[0_1px_0_rgb(var(--line)),0_24px_48px_-32px_rgb(18_26_51/0.45)] md:p-6",
        className,
      )}
    >
      {children}
    </div>
  );
}

function Feature({
  title,
  body,
  facts,
  href,
  cta,
  flip,
  children,
}: {
  title: string;
  body: string;
  facts: string[];
  href: string;
  cta: string;
  flip?: boolean;
  children: React.ReactNode;
}) {
  return (
    <article className="grid items-center gap-8 py-14 md:grid-cols-12 md:gap-12 md:py-20">
      <div className={cn("md:col-span-5", flip && "md:order-2 md:col-start-8")}>
        <h3 className="font-display text-[1.75rem] font-bold leading-[1.1] tracking-tight text-balance md:text-[2.125rem]">
          {title}
        </h3>
        <p className="mt-4 max-w-[52ch] leading-relaxed text-ink-soft">{body}</p>
        <ul className="mt-5 flex flex-col gap-2">
          {facts.map((f) => (
            <li key={f} className="flex gap-2.5">
              <Check aria-hidden className="mt-1 size-4 shrink-0 text-stamp" strokeWidth={2.5} />
              {f}
            </li>
          ))}
        </ul>
        <Link href={href} className="mt-6 inline-flex min-h-11 items-center gap-1 font-semibold text-pen hover:underline">
          {cta}
          <ArrowUpRight aria-hidden className="size-4" />
        </Link>
      </div>
      <div className={cn("md:col-span-7", flip && "md:order-1 md:col-start-1")}>{children}</div>
    </article>
  );
}

export default function Landing() {
  return (
    <div className="bg-paper text-ink">
      {/* ---------- Hero ---------- */}
      <section className="relative overflow-hidden bg-night text-white">
        {/* faint ledger ruling, the one texture on the page */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-[0.07]"
          style={{
            backgroundImage:
              "linear-gradient(90deg, transparent 0 96px, rgb(232 106 94) 96px 97px, transparent 97px), repeating-linear-gradient(transparent 0 35px, white 35px 36px)",
          }}
        />
        <header className="relative mx-auto flex max-w-6xl items-center justify-between px-4 py-4 md:px-8">
          <Link href="/" className="flex min-h-11 items-center gap-2 font-semibold">
            <Image src="/icon.svg" alt="" width={28} height={28} className="size-7" />
            Udyam Digital
          </Link>
          <nav aria-label="Main" className="flex items-center gap-1 text-sm text-white/80">
            <a href="#problem" className="hidden min-h-11 items-center rounded-bill px-3 hover:text-white md:flex">
              The problem
            </a>
            <a href="#solution" className="hidden min-h-11 items-center rounded-bill px-3 hover:text-white md:flex">
              How it works
            </a>
            <Link href="/console/login" className="hidden min-h-11 items-center rounded-bill px-3 hover:text-white sm:flex">
              Partner console
            </Link>
            <Link href="/judge" className="flex min-h-11 items-center rounded-bill px-3 font-medium text-white hover:bg-white/10">
              Judge challenge
            </Link>
            {REPO && (
              <a href={REPO} className="flex min-h-11 items-center gap-1 rounded-bill px-3 hover:text-white">
                Code <ArrowUpRight aria-hidden className="size-3.5" />
              </a>
            )}
          </nav>
        </header>

        <div className="relative mx-auto grid max-w-6xl grid-cols-[minmax(0,1fr)] items-center gap-6 px-4 pb-16 pt-8 md:grid-cols-[minmax(0,1fr)_480px] md:gap-12 md:px-8 md:pb-24 md:pt-14">
          <div className="max-w-xl">
            <h1 className="font-display text-[2.75rem] font-extrabold leading-[0.98] tracking-[-0.03em] text-balance md:text-[3.5rem] lg:text-[4rem]">
              Connect a small business in one sitting, from the owner&apos;s phone.
            </h1>
            <p className="mt-6 max-w-[50ch] text-lg leading-relaxed text-white/75">
              Shops, clinics and workshops ask for business internet every day. Today 7.4% of them end up connected, 17.6
              days later. Udyam Digital moves the whole journey onto the owner&apos;s phone, from the first question to the
              engineer&apos;s visit.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/start" className={ctaPrimary}>
                Try the owner app
              </Link>
              <Link href="/judge" className={ctaGhost}>
                Break a quote
              </Link>
            </div>
            <ApiStatus className="mt-6 text-white/60" />
          </div>
          <ExplodedPhone />
        </div>
      </section>

      {/* ---------- Problem ---------- */}
      <section id="problem" className="mx-auto max-w-6xl scroll-mt-4 px-4 py-16 md:px-8 md:py-24">
        <div className="grid gap-10 md:grid-cols-12">
          <div className="md:col-span-7">
            <h2 className="font-display text-[2.25rem] font-bold leading-[1.05] tracking-tight text-balance md:text-[3.25rem]">
              5,000 businesses asked. 368 got connected.
            </h2>
            <p className="mt-5 max-w-[56ch] text-lg leading-relaxed text-ink-soft">
              Every small-business lead from April to June 2026, by the stage it reached and the reason it stopped. Each
              box is the businesses still in; its red end is the ones lost at that stage.
            </p>
          </div>
          <dl className="grid content-end gap-5 sm:grid-cols-3 md:col-span-5 md:grid-cols-1 md:pl-8">
            {[
              ["17.6 days", "from first contact to a working connection"],
              ["3 calls", "from the owner, chasing an update"],
              ["₹15,053", "in sales cost for each connected business"],
            ].map(([v, l]) => (
              <div key={v} className="border-l-2 border-alert pl-4">
                <dt className="money font-display text-2xl font-bold tracking-tight">{v}</dt>
                <dd className="text-sm text-ink-soft">{l}</dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="mt-12">
          <Funnel3D />
        </div>

        <p className="mt-12 max-w-[30ch] font-display text-[1.75rem] font-bold leading-[1.15] tracking-tight md:text-[2.5rem]">
          {PROCESS_LOST.toLocaleString("en-IN")} of them didn&apos;t leave over the product. They left over a visit, a wait
          or paperwork.
        </p>
        <p className="mt-3 text-sm text-ink-soft">Those reasons are in bold above.</p>
      </section>

      {/* ---------- Solution: the bill ---------- */}
      <section id="solution" className="scroll-mt-4 border-t border-line bg-[rgb(var(--line)/0.35)]">
        <div className="mx-auto max-w-6xl px-4 py-16 md:px-8 md:py-24">
          <h2 className="max-w-[20ch] font-display text-[2.25rem] font-bold leading-[1.05] tracking-tight text-balance md:text-[3.25rem]">
            So the whole journey moves onto the phone.
          </h2>
          <p className="mt-5 max-w-[56ch] text-lg leading-relaxed text-ink-soft">
            Five things the owner does alone, in one sitting. Each one replaces a step of the old journey that lost
            businesses.
          </p>

          <div className={cn(s.bill, "mt-12 rounded-sm px-5 py-8 md:px-10 md:py-10")}>
            <div className="hidden grid-cols-[2.5rem_minmax(0,1.3fr)_minmax(0,1fr)] gap-8 border-b-2 border-ink pb-3 text-sm font-semibold md:grid">
              <span aria-hidden />
              <span>The owner, on the phone</span>
              <span>Replaces</span>
            </div>
            <ol>
              {BILL.map((b, i) => (
                <li
                  key={b.now}
                  className="grid gap-x-8 gap-y-3 border-b border-dashed border-line py-6 last:border-b-0 md:grid-cols-[2.5rem_minmax(0,1.3fr)_minmax(0,1fr)]"
                >
                  <span className="money font-display text-2xl font-bold text-pen">{i + 1}</span>
                  <div>
                    <p className="text-lg font-semibold">{b.now}</p>
                    <p className="mt-1 max-w-[56ch] leading-relaxed text-ink-soft">{b.how}</p>
                  </div>
                  <div>
                    <p className={cn(s.strike, "font-medium text-ink-soft")}>{b.was}</p>
                    <p className="mt-1 text-sm text-ink-soft">
                      <span className="money font-semibold text-alert">{b.lost.toLocaleString("en-IN")} lost</span>: {b.why}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
            <div className="mt-2 flex flex-wrap items-baseline justify-between gap-3 border-t-2 border-ink pt-4">
              <span className="font-semibold">Businesses lost to the steps it replaces</span>
              <span className="money font-display text-3xl font-bold">{PROCESS_LOST.toLocaleString("en-IN")}</span>
            </div>
          </div>
        </div>
      </section>

      {/* ---------- Features ---------- */}
      <section aria-labelledby="features" className="mx-auto max-w-6xl px-4 pt-16 md:px-8 md:pt-24">
        <h2 id="features" className="max-w-[22ch] font-display text-[2.25rem] font-bold leading-[1.05] tracking-tight md:text-[3.25rem]">
          What does the work behind each step
        </h2>

        <div className="divide-y divide-line">
          <Feature
            title="An advisor that asks only what it can't look up"
            body="It reads the business from the GST and Udyam registries, asks for what's missing, and hands the answers to a rules engine that decides what the business may buy. The language model only reads free text and phrases replies. It never picks a product."
            facts={[
              "English, Hindi and Hinglish, typed or spoken",
              "At most six questions to a recommended plan",
              "Site surveys and “call me” go to a person, with the chat attached",
            ]}
            href="/chat"
            cta="Talk to the advisor"
          >
            <Fragment className="flex flex-col gap-3 bg-paper">
              <p className="ml-auto max-w-[80%] rounded-2xl rounded-tr-sm bg-[rgb(42_58_143)] px-4 py-2.5 text-white">
                हमारी किराना दुकान है नागपुर में, 3 लोग हैं, GST नहीं है
              </p>
              <p className="max-w-[85%] rounded-2xl rounded-tl-sm bg-surface px-4 py-2.5 shadow-sm">
                ठीक है। बिना GST के भी प्लान मिल सकता है। आपको इंटरनेट किस काम के लिए चाहिए?
              </p>
              <div className="flex flex-wrap gap-2">
                {["UPI और बिलिंग", "CCTV", "WhatsApp पर ऑर्डर"].map((c) => (
                  <span key={c} className="rounded-full border border-pen/30 bg-surface px-3 py-1.5 text-pen">
                    {c}
                  </span>
                ))}
              </div>
              <p className="mt-1 border-t border-line pt-3 text-xs text-ink-soft">
                Rules applied: no GSTIN, so products that need GST are left out; tier-2 city, so Biz Fibre 1G is not offered.
              </p>
            </Fragment>
          </Feature>

          <Feature
            flip
            title="When the budget changes, the plan is repaired"
            body="Owners say “too expensive” or “we're opening a second shop”. The engine names what broke and the rule behind it, then offers the smallest valid fix, a clear trade-off, or a specialist who keeps the need on file."
            facts={[
              "Every option is re-checked by the rules engine",
              "Every solvable random broken quote fixed (564 of 564)",
              "Never cuts the internet connection to save money",
            ]}
            href="/judge"
            cta="Try to break a quote"
          >
            <Fragment>
              <div className="flex flex-wrap items-center gap-2 text-ink-soft">
                <span className="rounded-full bg-paper px-3 py-1">Budget ₹5,000</span>
                <span className="rounded-full bg-paper px-3 py-1">+ Backup 4G/5G Failover, essential</span>
              </div>
              <p className="mt-4">
                This comes to <span className="money font-semibold">₹5,905</span> a month,{" "}
                <span className="money font-semibold text-alert">₹905 over</span> your budget.
              </p>
              <div className="mt-4 rounded-bill border-2 border-pen p-4">
                <p className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="font-semibold">
                    Smallest change that fits
                    <span className="ml-2 inline-flex items-center gap-1 text-xs font-medium text-[rgb(176_120_8)]">
                      <span aria-hidden className="size-2 rounded-full bg-marigold" /> Recommended
                    </span>
                  </span>
                  <span className="money">
                    <span className="font-display text-xl font-bold">₹4,885</span>
                    <span className="text-ink-soft">/mo</span>
                  </span>
                </p>
                <ul className="mt-3 flex flex-col gap-1.5">
                  <li className="flex items-center gap-2">
                    <Plus aria-hidden className="size-3.5 text-pen" /> Backup 4G/5G Failover, you asked for it
                  </li>
                  <li className="flex items-center gap-2">
                    <Minus aria-hidden className="size-3.5 text-alert" /> Business Postpaid 599 to 299 × 3, to save money
                  </li>
                </ul>
                <p className="mt-3 text-xs font-medium text-stamp">Rules engine re-check: 0 ineligible products, dependencies OK</p>
              </div>
            </Fragment>
          </Feature>

          <Feature
            title="Documents checked while the owner waits"
            body="Consent comes first. Each photo is type-checked, read by OCR, compared with the registry and with the other documents, and given a verdict with a reason. Anything a machine shouldn't decide alone goes to a person in the console."
            facts={[
              "12 of 12 planted problems caught, each with its reason",
              "Blurred, tilted and watermarked photos handled",
              "Images encrypted, and deleted after verification",
            ]}
            href="/start"
            cta="Upload the sample documents"
          >
            <Fragment className="p-0 md:p-0">
              <ul className="divide-y divide-line">
                {[
                  ["GST certificate", "Matches the registry: name, GSTIN and status Active", true],
                  ["Udyam certificate", "Same business name as the GST certificate", true],
                  ["Signatory ID", "Name matches the authorised signatory", true],
                  ["Address proof", "The bill is 257 days old. Upload one from the last 90 days.", false],
                ].map(([doc, note, ok]) => (
                  <li key={doc as string} className="flex items-start gap-3 px-5 py-4">
                    <span
                      className={cn(
                        "mt-0.5 grid size-6 shrink-0 place-items-center rounded-full text-white",
                        ok ? "bg-stamp" : "bg-alert",
                      )}
                    >
                      {ok ? <Check aria-hidden className="size-3.5" strokeWidth={3} /> : <X aria-hidden className="size-3.5" strokeWidth={3} />}
                    </span>
                    <span>
                      <span className="block font-semibold">
                        {doc}
                        <span className="sr-only">{ok ? ", passed" : ", needs a new upload"}</span>
                      </span>
                      <span className={cn(ok ? "text-ink-soft" : "text-alert")}>{note}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </Fragment>
          </Feature>

          <Feature
            flip
            title="Nobody has to call to ask where the order is"
            body="The order moves through placed, documents verified, engineer booked, installed and working. Every change sends a WhatsApp message with a link back to the tracker, where the owner can move the engineer's visit."
            facts={[
              "Expected activation date from the first minute",
              "Verified documents move the order on by themselves",
              "On hold always comes with a reason",
            ]}
            href="/start"
            cta="See the tracker"
          >
            <div className="grid gap-4 sm:grid-cols-[1fr_1.1fr]">
              <Fragment>
                <ol className="flex flex-col">
                  {[
                    ["Order placed", "done"],
                    ["Documents verified", "done"],
                    ["Engineer visit booked", "now"],
                    ["Installed", "next"],
                    ["Working", "next"],
                  ].map(([step, state], i, all) => (
                    <li key={step} className="relative flex gap-3 pb-4 last:pb-0">
                      {i < all.length - 1 && (
                        <span
                          aria-hidden
                          className={cn("absolute left-[9px] top-5 h-full w-0.5", state === "done" ? "bg-stamp" : "bg-line")}
                        />
                      )}
                      <span
                        className={cn(
                          "relative z-10 mt-0.5 grid size-5 shrink-0 place-items-center rounded-full border-2",
                          state === "done" && "border-stamp bg-stamp text-white",
                          state === "now" && "border-pen bg-surface",
                          state === "next" && "border-line bg-surface",
                        )}
                      >
                        {state === "done" && <Check aria-hidden className="size-3" strokeWidth={3} />}
                        {state === "now" && <span className="size-2 rounded-full bg-pen" />}
                      </span>
                      <span className={cn(state === "next" ? "text-ink-soft" : "font-semibold")}>
                        {step}
                        {state === "now" && <span className="block text-sm font-normal text-ink-soft">Thursday, 10 am to 12 pm</span>}
                      </span>
                    </li>
                  ))}
                </ol>
              </Fragment>
              <div className="flex flex-col justify-center gap-3 rounded-xl bg-[rgb(236_229_221)] p-4 text-[rgb(17_27_33)]">
                {[
                  ["Payment received. Your order is placed, expected working in about 5 days.", "10:02"],
                  ["Documents verified. Engineer visit booked for Thursday, 10 am to 12 pm.", "10:42"],
                ].map(([msg, t]) => (
                  <p key={t} className="rounded-xl rounded-tl-sm bg-white p-3 text-sm shadow-sm">
                    {msg}
                    <span className="mt-1 flex items-center justify-end gap-1 text-[11px] text-[rgb(102_119_129)]">
                      {t} <CheckCheck aria-hidden className="size-3.5 text-[rgb(83_189_235)]" />
                    </span>
                  </p>
                ))}
              </div>
            </div>
          </Feature>

          <Feature
            title="Leads that need a person reach the right one"
            body="Reps and partners see their own territory's leads, ranked by how likely each is to activate and why, with where the journey stopped and the chat itself. They assign, follow up, clear KYC reviews and move installs along."
            facts={[
              "Each score shows its top three reasons",
              "Scoped by role and city, every view audited",
              "Funnel and cost per activation, live",
            ]}
            href="/console/login"
            cta="Open the partner console"
          >
            <Fragment className="p-0 md:p-0">
              <div className="flex items-center justify-between border-b border-line px-5 py-3 text-ink-soft">
                <span className="font-semibold text-ink">Waiting for a call</span>
                <span>Pune</span>
              </div>
              {[
                ["Clinic, 8 people", "Asked for a leased line: needs a site survey", 0.71, ["referral lead", "has GSTIN", "1 site"]],
                ["Bakery, 2 outlets", "Asked to talk to a person", 0.58, ["2 sites", "tier-1 city", "no current provider"]],
              ].map(([name, why, score, reasons]) => (
                <div key={name as string} className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 border-b border-line px-5 py-4 last:border-b-0">
                  <span className="font-semibold">{name as string}</span>
                  <span className="money row-span-2 self-center font-display text-2xl font-bold text-pen">
                    {Math.round((score as number) * 100)}%
                  </span>
                  <span className="text-ink-soft">{why as string}</span>
                  <span className="col-span-2 mt-1 flex flex-wrap gap-1.5">
                    {(reasons as string[]).map((r) => (
                      <span key={r} className="rounded-full bg-paper px-2.5 py-0.5 text-xs text-ink-soft">
                        + {r}
                      </span>
                    ))}
                  </span>
                </div>
              ))}
            </Fragment>
          </Feature>
        </div>
      </section>

      {/* ---------- Proof ---------- */}
      <section className="bg-night text-white">
        <div className="mx-auto grid max-w-6xl gap-12 px-4 py-16 md:grid-cols-12 md:px-8 md:py-24">
          <div className="md:col-span-5">
            <h2 className="font-display text-[2.25rem] font-bold leading-[1.05] tracking-tight text-balance md:text-[3rem]">
              We tried to break it before you do.
            </h2>
            <p className="mt-5 max-w-[46ch] leading-relaxed text-white/70">
              Every number here comes from a test you can re-run. The judge challenge shows the same scorecard, next to a
              quote you can break yourself.
            </p>
            <Link href="/judge" className={cn(ctaPrimary, "mt-8")}>
              Open the judge challenge
            </Link>
            <p className="mt-8 max-w-[46ch] text-sm leading-relaxed text-white/60">
              Consent before KYC, identifiers masked in every log, GSTIN and documents encrypted, and every staff view of a
              lead audited.
            </p>
          </div>
          <dl className="md:col-span-7">
            {PROOF.map(([n, what]) => (
              <div key={n} className="grid gap-1 border-t border-white/15 py-5 sm:grid-cols-[11rem_1fr] sm:gap-6">
                <dt className="money font-display text-3xl font-bold tracking-tight text-marigold">{n}</dt>
                <dd className="leading-relaxed text-white/80 sm:pt-1.5">{what}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      {/* ---------- Try it ---------- */}
      <section id="try" className="mx-auto grid max-w-6xl scroll-mt-4 gap-12 px-4 py-16 md:grid-cols-12 md:px-8 md:py-24">
        <div className="md:col-span-7">
          <h2 className="font-display text-[2rem] font-bold leading-[1.1] tracking-tight md:text-[2.5rem]">
            Run the whole journey in two minutes
          </h2>
          <ol className="mt-8 flex flex-col gap-5">
            {[
              <>
                Open the <Link href="/chat" className="font-semibold text-pen hover:underline">advisor</Link> and describe a
                business, for example “Furniture workshop in Nagpur, 12 workers, GSTIN 27XUIXG0767D1ZP, need email”.
              </>,
              <>Open the plan, switch an add-on, and pay in test mode with any 10-digit mobile number.</>,
              <>
                Upload the four documents that pass. The order moves to “Documents verified”. Swap in the old address proof to
                see it caught.
              </>,
              <>
                Sign in to the <Link href="/console/login" className="font-semibold text-pen hover:underline">console</Link>{" "}
                as <code className="rounded bg-surface px-1.5 py-0.5 text-sm">admin</code> and advance the install. The
                tracker updates by itself.
              </>,
            ].map((step, i) => (
              <li key={i} className="grid grid-cols-[2rem_1fr] gap-3 leading-relaxed">
                <span className="money font-display text-xl font-bold text-pen">{i + 1}</span>
                <span className="text-ink-soft">{step}</span>
              </li>
            ))}
          </ol>
          <p className="mt-8 text-sm text-ink-soft">
            Console password: ask the team, or <code className="rounded bg-surface px-1.5 py-0.5">udyam-demo</code> on a local
            run. API reference: <a href={API_DOCS} className="font-medium text-pen hover:underline">interactive docs</a>.
          </p>
        </div>
        <div className="md:col-span-5">
          <h3 className="font-semibold">Sample documents</h3>
          <p className="mt-1 text-sm text-ink-soft">Synthetic specimens from the case data.</p>
          <ul className="mt-4 divide-y divide-line rounded-xl bg-surface shadow-[0_1px_0_rgb(var(--line))]">
            {SAMPLES.map(([file, label, result]) => (
              <li key={file}>
                <a
                  href={`/samples/${file}`}
                  download
                  className="flex min-h-12 items-center justify-between gap-3 px-4 transition-colors hover:bg-paper"
                >
                  <span>
                    {label}
                    <span className={cn("ml-2 text-sm", result === "fails" ? "text-alert" : "text-stamp")}>{result}</span>
                  </span>
                  <Download aria-hidden className="size-4 shrink-0 text-ink-soft" />
                </a>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* ---------- Architecture ---------- */}
      <section className="border-t border-line">
        <div className="mx-auto max-w-6xl px-4 py-16 md:px-8">
          <h2 className="font-display text-[2rem] font-bold leading-[1.1] tracking-tight md:text-[2.5rem]">How it fits together</h2>
          <p className="mt-4 max-w-[64ch] leading-relaxed text-ink-soft">
            Every channel calls one API, and every recommendation and price passes through the deterministic rules engine.
            The AI is optional: with no key, the advisor runs on its own rules and the demo never depends on a network call.
          </p>
          <div className="mt-8 overflow-x-auto rounded-xl bg-surface p-2 shadow-[0_1px_0_rgb(var(--line))]">
            <Image
              src="/architecture.png"
              alt="Architecture: owner app, voice, WhatsApp and partner console call one FastAPI backend; services for the advisor, rules engine, quotes, Smart KYC, order tracker and propensity score; Postgres, case data, object store and a worker; optional Gemini/OpenAI, registry APIs, Razorpay and WhatsApp."
              width={2560}
              height={1600}
              className="h-auto min-w-[720px] rounded-lg"
            />
          </div>
        </div>
      </section>

      <footer className="bg-night text-white/70">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-8 text-sm md:px-8">
          <span className="font-semibold text-white">Udyam Digital</span>
          <nav aria-label="Footer" className="flex flex-wrap gap-x-5 gap-y-2">
            <Link href="/start" className="hover:text-white">
              Owner app
            </Link>
            <Link href="/console/login" className="hover:text-white">
              Partner console
            </Link>
            <Link href="/judge" className="hover:text-white">
              Judge challenge
            </Link>
            <a href={API_DOCS} className="hover:text-white">
              API docs
            </a>
          </nav>
        </div>
      </footer>
    </div>
  );
}
