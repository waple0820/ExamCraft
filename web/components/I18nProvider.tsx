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
  DEFAULT_LOCALE,
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

// Provider takes ONLY the locale string from the server side. The messages
// object contains template functions (e.g. `createdAt(date) => string`),
// which React cannot serialize across the server → client boundary, so we
// look them up here on the client from the bundled dictionaries instead.
export function I18nProvider({
  locale,
  children,
}: {
  locale: Locale;
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
    () => ({
      locale,
      messages: messagesByLocale[locale],
      setLocale,
    }),
    [locale, setLocale],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): Ctx {
  const ctx = useContext(I18nContext);
  if (ctx) return ctx;
  // Fallback if a client component renders outside the provider (e.g. early
  // mount during a hot reload). Defaults to zh so nothing crashes.
  return {
    locale: DEFAULT_LOCALE,
    messages: messagesByLocale[DEFAULT_LOCALE],
    setLocale: () => {
      /* no-op outside provider */
    },
  };
}
