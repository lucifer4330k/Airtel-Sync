import { cva, type VariantProps } from "class-variance-authority";
import Link from "next/link";
import { forwardRef, type ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export const buttonVariants = cva(
  "inline-flex min-h-12 items-center justify-center gap-2 rounded-bill px-5 text-base font-semibold transition-colors duration-150 disabled:pointer-events-none disabled:opacity-50 cursor-pointer",
  {
    variants: {
      variant: {
        primary: "bg-pen text-white hover:bg-pen-strong dark:text-paper",
        quiet: "border border-line bg-surface text-ink hover:border-pen hover:text-pen",
        link: "min-h-11 px-0 text-pen underline-offset-4 hover:underline",
      },
      width: { full: "w-full", auto: "" },
    },
    defaultVariants: { variant: "primary", width: "auto" },
  },
);

type Variants = VariantProps<typeof buttonVariants>;

export const Button = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement> & Variants>(
  ({ className, variant, width, ...props }, ref) => (
    <button ref={ref} className={cn(buttonVariants({ variant, width }), className)} {...props} />
  ),
);
Button.displayName = "Button";

export function ButtonLink({
  href,
  className,
  variant,
  width,
  children,
}: { href: string; className?: string; children: React.ReactNode } & Variants) {
  return (
    <Link href={href} className={cn(buttonVariants({ variant, width }), className)}>
      {children}
    </Link>
  );
}
