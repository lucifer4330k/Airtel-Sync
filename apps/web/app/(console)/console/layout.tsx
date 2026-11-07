import Image from "next/image";
import { BarChart3, ClipboardCheck, Users } from "lucide-react";
import Link from "next/link";

const NAV = [
  { href: "/console", label: "Funnel", icon: BarChart3 },
  { href: "/console", label: "Leads", icon: Users },
  { href: "/console", label: "KYC review queue", icon: ClipboardCheck },
];

export default function ConsoleLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-dvh md:grid md:grid-cols-[14rem_1fr]">
      <aside className="border-b border-line bg-surface px-4 py-3 md:border-b-0 md:border-r md:py-6">
        <p className="mb-4 flex items-center gap-2 font-semibold">
          <Image src="/icon.svg" alt="" width={28} height={28} className="size-6" />
          Partner console
        </p>
        <nav className="flex gap-1 overflow-x-auto md:flex-col">
          {NAV.map(({ href, label, icon: Icon }) => (
            <Link
              key={label}
              href={href}
              className="flex min-h-11 shrink-0 items-center gap-2 rounded-bill px-3 text-sm text-ink-soft hover:bg-paper hover:text-ink"
            >
              <Icon aria-hidden className="size-4" />
              {label}
            </Link>
          ))}
        </nav>
      </aside>
      <main className="px-4 py-6 md:px-8">{children}</main>
    </div>
  );
}
