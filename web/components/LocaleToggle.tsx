"use client";

import { LOCALES, type Locale } from "@/lib/i18n";
import { cn } from "@/lib/cn";

import { useI18n } from "@/components/I18nProvider";

const LABEL: Record<Locale, string> = { zh: "中", en: "EN" };

export function LocaleToggle() {
  const { locale, setLocale, messages } = useI18n();
  return (
    <div
      role="group"
      aria-label={messages.locale.switchLabel}
      className="flex items-center gap-0.5 rounded-full border border-ink/10 bg-white/50 p-0.5"
    >
      {LOCALES.map((l) => (
        <button
          key={l}
          type="button"
          onClick={() => setLocale(l)}
          aria-pressed={locale === l}
          className={cn(
            "rounded-full px-2.5 py-0.5 text-[11px] font-medium uppercase tracking-wider transition",
            locale === l
              ? "bg-ink text-ivory"
              : "text-ink/45 hover:text-ink",
          )}
        >
          {LABEL[l]}
        </button>
      ))}
    </div>
  );
}
