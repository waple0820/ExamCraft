import { cookies } from "next/headers";

import {
  DEFAULT_LOCALE,
  LOCALE_COOKIE,
  LOCALES,
  type Locale,
  type Messages,
  messagesByLocale,
} from "@/lib/i18n";

export async function getLocale(): Promise<Locale> {
  const jar = await cookies();
  const v = jar.get(LOCALE_COOKIE)?.value;
  if (v && (LOCALES as readonly string[]).includes(v)) {
    return v as Locale;
  }
  return DEFAULT_LOCALE;
}

export async function getMessages(): Promise<{
  locale: Locale;
  messages: Messages;
}> {
  const locale = await getLocale();
  return { locale, messages: messagesByLocale[locale] };
}
