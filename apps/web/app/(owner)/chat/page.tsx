"use client";

import { Mic, MicOff, SendHorizontal, Volume2, VolumeX } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { advisor, owner, plan, type BundleCard } from "@/lib/journey";
import { cn, formatINR } from "@/lib/utils";
import { useSpeech } from "@/lib/use-speech";

type Msg = { from: "advisor" | "owner"; text: string };

export default function ChatPage() {
  const t = useTranslations("chat");
  const tq = useTranslations("quote");
  const locale = useLocale();
  const router = useRouter();

  const [session, setSession] = useState<{ id: number; token: string } | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [chips, setChips] = useState<string[]>([]);
  const [card, setCard] = useState<BundleCard | null>(null);
  const [humanFlag, setHumanFlag] = useState(false);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [speak, setSpeak] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const started = useRef(false);

  const speech = useSpeech(locale === "hi" ? "hi-IN" : "en-IN");

  const addAdvisor = useCallback(
    (text: string) => {
      setMessages((m) => [...m, { from: "advisor", text }]);
      if (speak) speech.say(text);
    },
    [speak, speech],
  );

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    advisor
      .start(locale === "hi" ? "hi" : "en")
      .then((s) => {
        setSession({ id: s.session_id, token: s.token });
        setMessages([{ from: "advisor", text: s.reply }]);
        setChips(s.chips);
      })
      .catch(() => setError(t("start_error")));
  }, [locale, t]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, card]);

  async function send(text: string) {
    const clean = text.trim();
    if (!clean || !session || busy) return;
    setMessages((m) => [...m, { from: "owner", text: clean }]);
    setInput("");
    setChips([]);
    setBusy(true);
    setError(null);
    try {
      const turn = await advisor.send(session.id, session.token, clean);
      addAdvisor(turn.reply);
      setChips(turn.chips);
      if (turn.needs_human) setHumanFlag(true);
      if (turn.bundle) {
        setCard(turn.bundle);
        owner.set({ businessId: turn.bundle.business_id, token: turn.bundle.owner_token });
        plan.set({ quoteIds: turn.bundle.quotes.map((q) => q.id), recommended: turn.bundle.recommended_quote_id });
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("start_error"));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (speech.transcript) {
      void send(speech.transcript);
      speech.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [speech.transcript]);

  return (
    <div className="flex flex-1 flex-col">
      <div className="mb-2 flex items-center justify-between">
        <h1 className="text-lg font-semibold">{t("title")}</h1>
        <button
          type="button"
          onClick={() => setSpeak((v) => !v)}
          aria-pressed={speak}
          className="flex min-h-11 cursor-pointer items-center gap-1.5 rounded-bill px-2 text-sm text-ink-soft hover:text-ink"
        >
          {speak ? <Volume2 aria-hidden className="size-4" /> : <VolumeX aria-hidden className="size-4" />}
          {t("read_aloud")}
        </button>
      </div>

      <ol className="flex flex-1 flex-col gap-3" aria-live="polite">
        {messages.map((m, i) => (
          <li
            key={i}
            className={cn(
              "max-w-[88%] whitespace-pre-line rounded-bill px-4 py-2.5",
              m.from === "advisor"
                ? "self-start border border-line bg-surface"
                : "self-end bg-pen text-white dark:text-paper",
            )}
          >
            {m.text}
          </li>
        ))}
        {busy && (
          <li className="self-start rounded-bill border border-line bg-surface px-4 py-2.5 text-ink-soft" aria-busy>
            …
          </li>
        )}
      </ol>

      {card && (
        <section className="mt-4 rounded-bill border border-line bg-surface p-4" aria-label={t("plan_title")}>
          <h2 className="font-semibold">{t("plan_title")}</h2>
          <ul className="mt-3 grid grid-cols-3 gap-2">
            {card.quotes.map((q) => (
              <li
                key={q.id}
                className={cn(
                  "rounded-bill border p-2 text-center",
                  q.id === card.recommended_quote_id ? "border-pen" : "border-line",
                )}
              >
                <p className="text-xs text-ink-soft">{tq(q.tier)}</p>
                <p className="money font-semibold">{formatINR(q.monthly_total)}</p>
              </li>
            ))}
          </ul>
          <Button width="full" className="mt-3" onClick={() => router.push(`/quote?q=${card.recommended_quote_id}`)}>
            {t("see_plan")}
          </Button>
        </section>
      )}
      {humanFlag && <p className="mt-3 text-sm text-ink-soft">{t("specialist")}</p>}
      {error && (
        <p role="alert" className="mt-3 text-sm text-alert">
          {error}
        </p>
      )}
      <div ref={endRef} />

      <div className="sticky bottom-0 mt-4 flex flex-col gap-3 bg-paper pb-2 pt-2">
        {chips.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {chips.map((c) => (
              <Button
                key={c}
                variant="quiet"
                onClick={() => send(c)}
                disabled={busy}
                className="min-h-11 px-4 text-sm font-medium"
              >
                {c}
              </Button>
            ))}
          </div>
        )}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void send(input);
          }}
          className="flex gap-2"
        >
          <label htmlFor="answer" className="sr-only">
            {t("placeholder")}
          </label>
          <input
            id="answer"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            autoComplete="off"
            placeholder={speech.listening ? t("listening") : t("placeholder")}
            className="min-h-12 min-w-0 flex-1 rounded-bill border border-line bg-surface px-4 text-base"
          />
          {speech.supported && (
            <Button
              type="button"
              variant="quiet"
              aria-label={speech.listening ? t("mic_stop") : t("mic_start")}
              aria-pressed={speech.listening}
              onClick={speech.listening ? speech.stop : speech.listen}
              className="px-3"
            >
              {speech.listening ? <MicOff aria-hidden className="size-5" /> : <Mic aria-hidden className="size-5" />}
            </Button>
          )}
          <Button type="submit" aria-label={t("send")} className="px-4" disabled={busy || !session}>
            <SendHorizontal aria-hidden className="size-5" />
          </Button>
        </form>
      </div>
    </div>
  );
}
