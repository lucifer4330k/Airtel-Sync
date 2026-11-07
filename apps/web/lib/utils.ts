import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });

/** ₹1,23,456 — Indian digit grouping. */
export function formatINR(value: number): string {
  return inr.format(value);
}

/** The case fixes "today" at 2026-07-15 for every date calculation. */
export const REFERENCE_DATE = new Date("2026-07-15T00:00:00+05:30");

export function addDays(date: Date, days: number): Date {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}
