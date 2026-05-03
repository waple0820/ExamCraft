"use client";

import { useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  type ReactNode,
} from "react";

import {
  LOCALE_COOKIE,
  type Locale,
  type Messages,
  messagesByLocale,
} from "@/lib/i18n";

type Ctx = {
  locale: Locale;
  messages: Messages;
  setLocale: (locale: Locale) => void;
};

const I18nContext = createContext<Ctx | null>(null);

export function I18nProvider({
  locale,
  messages,
  children,
}: {
  locale: Locale;
  messages: Messages;
  children: ReactNode;
}) {
  const router = useRouter();

  const setLocale = useCallback(
    (next: Locale) => {
      // 1 year persistence; cookie is readable by SSR for getLocale().
      document.cookie = `${LOCALE_COOKIE}=${next}; path=/; max-age=${60 * 60 * 24 * 365}; SameSite=Lax`;
      router.refresh();
    },
    [router],
  );

  const value = useMemo<Ctx>(
    () => ({ locale, messages, setLocale }),
    [locale, messages, setLocale],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): Ctx {
  const ctx = useContext(I18nContext);
  if (ctx) return ctx;
  // Fallback for the rare case the provider hasn't mounted (e.g. server-only
  // boundary). Return zh defaults so we never crash on first render.
  return {
    locale: "zh",
    messages: messagesByLocale.zh,
    setLocale: () => {
      /* no-op outside provider */
    },
  };
}
