"use client";

import { SendHorizontal } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { Button, ButtonLink } from "@/components/ui/button";
import type { Segment } from "@/lib/api";
import { cn } from "@/lib/utils";

/*
 * Scripted slot-filling for now: the same five slots the LangChain advisor
 * will fill. When POST /advisor/sessions/{id}/messages lands, the question
 * logic moves server-side and this screen only renders turns.
 */

type Slot = "segment" | "employees" | "sites" | "city_tier" | "gstin";
type Msg = { from: "advisor" | "owner"; text: string };
type Answers = Partial<{ segment: Segment; employees: number; sites: number; city_tier: 1 | 2; gstin: string }>;

const ORDER: Slot[] = ["segment", "employees", "sites", "city_tier", "gstin"];
const QUESTION: Record<Slot, string> = {
  segment: "q_type",
  employees: "q_employees",
  sites: "q_sites",
  city_tier: "q_city",
  gstin: "q_gstin",
};

export default function ChatPage() {
  const t = useTranslations("chat");
  const [answers, setAnswers] = useState<Answers>({});
  const [messages, setMessages] = useState<Msg[]>([{ from: "advisor", text: t("q_type") }]);
  const [input, setInput] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  const pending = ORDER.find((s) => !(s in answers));
  const done = pending === undefined;

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  function record(slot: Slot, value: Answers[Slot] | "", shown: string) {
    const next = { ...answers, [slot]: value };
    setAnswers(next);
    const nextSlot = ORDER.find((s) => !(s in next));
    setMessages((m) => [
      ...m,
      { from: "owner", text: shown },
      { from: "advisor", text: nextSlot ? t(QUESTION[nextSlot]) : t("done") },
    ]);
    setInput("");
  }

  function submitText(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || !pending) return;
    if (pending === "employees" || pending === "sites") {
      const n = Number.parseInt(text, 10);
      if (!Number.isFinite(n) || n < 1) {
        setMessages((m) => [...m, { from: "owner", text }, { from: "advisor", text: t("invalid_number") }]);
        setInput("");
        return;
      }
      record(pending, n, String(n));
    } else if (pending === "gstin") {
      record("gstin", text.toUpperCase(), text.toUpperCase());
    }
  }

  const quoteHref = done
    ? `/quote?${new URLSearchParams({
        segment: answers.segment!,
        city_tier: String(answers.city_tier),
        employees: String(answers.employees),
        sites: String(answers.sites),
        ...(answers.gstin ? { gstin: answers.gstin } : {}),
      })}`
    : "";

  const chips: { label: string; act: () => void }[] =
    pending === "segment"
      ? (["micro", "prof", "multi", "mfg"] as Segment[]).map((s) => ({
          label: t(`type_${s}`),
          act: () => record("segment", s, t(`type_${s}`)),
        }))
      : pending === "city_tier"
        ? ([1, 2] as const).map((c) => ({ label: t(`city_${c}`), act: () => record("city_tier", c, t(`city_${c}`)) }))
        : pending === "gstin"
          ? [{ label: t("no_gstin"), act: () => record("gstin", "", t("no_gstin")) }]
          : pending === "sites"
            ? [1, 2, 5].map((n) => ({ label: String(n), act: () => record("sites", n, String(n)) }))
            : [];

  return (
    <div className="flex flex-1 flex-col">
      <h1 className="sr-only">{t("title")}</h1>
      <ol className="flex flex-1 flex-col gap-3" aria-live="polite">
        {messages.map((m, i) => (
          <li
            key={i}
            className={cn(
              "max-w-[85%] rounded-bill px-4 py-2.5",
              m.from === "advisor" ? "self-start border border-line bg-surface" : "self-end bg-pen text-white dark:text-paper",
            )}
          >
            {m.text}
          </li>
        ))}
        <div ref={endRef} />
      </ol>

      <div className="sticky bottom-0 mt-4 flex flex-col gap-3 bg-paper pb-2 pt-2">
        {done ? (
          <ButtonLink href={quoteHref} width="full">
            {t("see_price")}
          </ButtonLink>
        ) : (
          <>
            {chips.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {chips.map((c) => (
                  <Button key={c.label} variant="quiet" onClick={c.act} className="min-h-11 px-4 text-sm font-medium">
                    {c.label}
                  </Button>
                ))}
              </div>
            )}
            {(pending === "employees" || pending === "sites" || pending === "gstin") && (
              <form onSubmit={submitText} className="flex gap-2">
                <label htmlFor="answer" className="sr-only">
                  {t("placeholder")}
                </label>
                <input
                  id="answer"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  inputMode={pending === "gstin" ? "text" : "numeric"}
                  autoComplete="off"
                  placeholder={t("placeholder")}
                  className="min-h-12 flex-1 rounded-bill border border-line bg-surface px-4 text-base"
                />
                <Button type="submit" aria-label={t("send")} className="px-4">
                  <SendHorizontal aria-hidden className="size-5" />
                </Button>
              </form>
            )}
          </>
        )}
      </div>
    </div>
  );
}
