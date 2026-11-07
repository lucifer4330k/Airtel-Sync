import { cookies } from "next/headers";
import { getRequestConfig } from "next-intl/server";

import { LOCALE_COOKIE, LOCALES, type Locale } from "./locales";

// Locale lives in a cookie (no /hi/ URL prefix): the owner picks a language
// once and every screen, including shared quote links, follows it.
export default getRequestConfig(async () => {
  const fromCookie = cookies().get(LOCALE_COOKIE)?.value;
  const locale: Locale = LOCALES.includes(fromCookie as Locale) ? (fromCookie as Locale) : "en";
  return {
    locale,
    messages: (await import(`../messages/${locale}.json`)).default,
  };
});
