"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";

import { LanguagePicker } from "@/components/language-picker";
import { cn } from "@/lib/utils";

// The owner journey is a real sequence, so the step bar is numbered.
const STEPS = [
  { key: "advisor", href: "/chat" },
  { key: "quote", href: "/quote" },
  { key: "kyc", href: "/kyc" },
  { key: "track", href: "/track/demo" },
] as const;

export function OwnerShell({ children }: { children: React.ReactNode }) {
  const t = useTranslations();
  const pathname = usePathname();
  const current = STEPS.findIndex((s) => pathname.startsWith(s.href.replace("/demo", "")));

  return (
    <div className="mx-auto flex min-h-dvh max-w-app flex-col px-4">
      <header className="flex items-center justify-between py-3">
        <Link href="/" className="flex min-h-11 items-center gap-2 font-semibold">
          <Image src="/icon.svg" alt="" width={28} height={28} className="size-7" />
          {t("app.name")}
        </Link>
        <LanguagePicker />
      </header>

      {current >= 0 && (
        <nav aria-label="Steps" className="mb-4">
          <ol className="grid grid-cols-4 gap-1">
            {STEPS.map((s, i) => (
              <li key={s.key}>
                <Link
                  href={s.href}
                  aria-current={i === current ? "step" : undefined}
                  className={cn(
                    "flex min-h-11 flex-col justify-end border-t-[3px] pt-1.5 text-xs",
                    i < current && "border-pen text-ink-soft",
                    i === current && "border-pen font-semibold text-pen",
                    i > current && "border-line text-ink-soft",
                  )}
                >
                  <span className="money">{i + 1}</span>
                  {t(`steps.${s.key}`)}
                </Link>
              </li>
            ))}
          </ol>
        </nav>
      )}

      <main className="flex flex-1 flex-col pb-8">{children}</main>
    </div>
  );
}
