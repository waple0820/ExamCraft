import { en } from "./messages/en";
import { zh, type Messages } from "./messages/zh";

export type Locale = "zh" | "en";
export const DEFAULT_LOCALE: Locale = "zh";
export const LOCALES: readonly Locale[] = ["zh", "en"] as const;
export const LOCALE_COOKIE = "examcraft_locale";

export const messagesByLocale: Record<Locale, Messages> = { zh, en };

export type { Messages };
