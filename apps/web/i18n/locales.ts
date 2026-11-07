// Marathi (mr) and Tamil (ta) are next: add messages/<code>.json and list them here.
export const LOCALES = ["en", "hi"] as const;
export type Locale = (typeof LOCALES)[number];
export const LOCALE_COOKIE = "NEXT_LOCALE";
export const LOCALE_LABELS: Record<Locale, string> = { en: "English", hi: "हिन्दी" };
