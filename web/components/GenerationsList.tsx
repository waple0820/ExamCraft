"use client";

import Link from "next/link";

import { useI18n } from "@/components/I18nProvider";
import type { GenerationSummary } from "@/lib/api";

export function GenerationsList({ items }: { items: GenerationSummary[] }) {
  const { messages: m, locale } = useI18n();

  const STATUS_COPY: Record<string, { label: string; tone: string }> = {
    queued: { label: m.generate.statusQueued, tone: "text-ink/45" },
    running: { label: m.generate.statusRunning, tone: "text-violet" },
    done: { label: m.generate.statusDone, tone: "text-teal" },
    failed: { label: m.generate.statusFailed, tone: "text-red-600" },
  };
  const dateLocale = locale === "zh" ? "zh-CN" : "en-US";

  if (items.length === 0) {
    return (
      <p className="mt-2 text-sm italic text-ink/40">{m.generate.historyEmpty}</p>
    );
  }
  return (
    <ul className="mt-4 divide-y divide-ink/5">
      {items.map((g) => {
        const status = STATUS_COPY[g.status] ?? STATUS_COPY.queued;
        return (
          <li key={g.id}>
            <Link
              href={`/generations/${g.id}` as never}
              className="flex items-center justify-between gap-4 py-4 transition hover:text-violet"
            >
              <div>
                <p className="text-sm font-medium">
                  {m.generate.historyTitle(
                    new Date(g.created_at).toLocaleString(dateLocale),
                  )}
                </p>
                <p className="mt-1 text-xs text-ink/45">
                  <span className={status.tone}>{status.label}</span>
                  {" · "}
                  {m.generate.pages(g.page_count)}
                  {g.status === "running" ? (
                    <> · {Math.round(g.progress_pct * 100)}%</>
                  ) : null}
                </p>
              </div>
              <span aria-hidden className="text-ink/30">
                →
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
