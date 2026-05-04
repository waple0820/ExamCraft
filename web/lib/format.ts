import type { Locale } from "@/lib/i18n";

const TIME_ZONE = "Asia/Shanghai";

function localeTag(locale: Locale): string {
  return locale === "zh" ? "zh-CN" : "en-US";
}

/** Date + time, e.g. "2026/5/4 14:32" (zh) or "5/4/2026, 2:32 PM" (en). */
export function formatDateTime(iso: string, locale: Locale): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString(localeTag(locale), {
    timeZone: TIME_ZONE,
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: locale === "en",
  });
}

/** Date only. */
export function formatDate(iso: string, locale: Locale): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString(localeTag(locale), {
    timeZone: TIME_ZONE,
    year: "numeric",
    month: "numeric",
    day: "numeric",
  });
}
