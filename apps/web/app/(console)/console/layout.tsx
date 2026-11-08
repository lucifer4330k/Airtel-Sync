"use client";

import { BarChart3, ClipboardCheck, LogOut, Truck, Users } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { consoleSession, type ConsoleUser } from "@/lib/console";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/console", label: "Funnel", icon: BarChart3 },
  { href: "/console/leads", label: "Leads", icon: Users },
  { href: "/console/kyc", label: "KYC review", icon: ClipboardCheck },
  { href: "/console/orders", label: "Orders", icon: Truck },
];

export default function ConsoleLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<ConsoleUser | null>(null);
  const isLogin = pathname === "/console/login";

  useEffect(() => {
    const s = consoleSession.get();
    if (!s && !isLogin) router.replace("/console/login");
    setUser(s?.user ?? null);
  }, [isLogin, router, pathname]);

  if (isLogin) return <>{children}</>;
  if (!user) return null;

  return (
    <div className="min-h-dvh md:grid md:grid-cols-[14rem_1fr]">
      <aside className="flex flex-col border-b border-line bg-surface px-4 py-3 md:sticky md:top-0 md:h-dvh md:border-b-0 md:border-r md:py-6">
        <p className="mb-4 flex items-center gap-2 font-semibold">
          <Image src="/icon.svg" alt="" width={28} height={28} className="size-6" />
          Partner console
        </p>
        <nav className="flex gap-1 overflow-x-auto md:flex-col">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = href === "/console" ? pathname === href : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex min-h-11 shrink-0 items-center gap-2 rounded-bill px-3 text-sm",
                  active ? "bg-paper font-semibold text-ink" : "text-ink-soft hover:bg-paper hover:text-ink",
                )}
              >
                <Icon aria-hidden className="size-4" />
                {label}
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto hidden pt-6 text-sm md:block">
          <p className="font-medium">{user.name}</p>
          <p className="text-ink-soft">
            {user.role}
            {user.city ? `, ${user.city}` : ""}
          </p>
          <button
            type="button"
            onClick={() => {
              consoleSession.set(null);
              router.replace("/console/login");
            }}
            className="mt-2 flex min-h-11 cursor-pointer items-center gap-2 text-ink-soft hover:text-ink"
          >
            <LogOut aria-hidden className="size-4" />
            Sign out
          </button>
        </div>
      </aside>
      <main className="min-w-0 px-4 py-6 md:px-8">{children}</main>
    </div>
  );
}
