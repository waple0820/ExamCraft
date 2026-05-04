"use client";

import { AnimatePresence, motion } from "framer-motion";
import { FileText } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { useI18n } from "@/components/I18nProvider";
import type { Sample, SampleStatus } from "@/lib/api";
import { backendUrl } from "@/lib/api";
import { clientDeleteSample } from "@/lib/client";
import { formatDateTime } from "@/lib/format";

const IN_FLIGHT: SampleStatus[] = ["uploaded", "extracting", "analyzing"];

export function SampleList({
  bankId,
  initialSamples,
}: {
  bankId: string;
  initialSamples: Sample[];
}) {
  const router = useRouter();
  const { messages: m, locale } = useI18n();
  const [samples, setSamples] = useState<Sample[]>(initialSamples);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);

  useEffect(() => {
    setSamples(initialSamples);
  }, [initialSamples]);

  const anyInFlight = useMemo(
    () => samples.some((s) => IN_FLIGHT.includes(s.status)),
    [samples],
  );

  useEffect(() => {
    if (!anyInFlight) return;
    let alive = true;
    const tick = async () => {
      try {
        const res = await fetch(backendUrl(`/api/banks/${bankId}/samples`), {
          credentials: "include",
          cache: "no-store",
        });
        if (!res.ok) return;
        const fresh = (await res.json()) as Sample[];
        if (!alive) return;
        setSamples(fresh);
        const stillRunning = fresh.some((s) => IN_FLIGHT.includes(s.status));
        if (!stillRunning) {
          // Refresh server components so the analysis panel re-renders.
          router.refresh();
        }
      } catch {
        // Ignore poll failures; we'll try again next tick.
      }
    };
    const id = setInterval(tick, 2000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [anyInFlight, bankId, router]);

  async function onDelete(id: string) {
    setPendingDelete(id);
    try {
      await clientDeleteSample(id);
      setSamples((prev) => prev.filter((s) => s.id !== id));
      router.refresh();
    } finally {
      setPendingDelete(null);
    }
  }

  const STATUS_COPY: Record<SampleStatus, { label: string; tone: string; dotTone: string }> = {
    uploaded: {
      label: m.sampleList.statusUploaded,
      tone: "text-ink/45",
      dotTone: "bg-ink/30",
    },
    extracting: {
      label: m.sampleList.statusExtracting,
      tone: "text-violet",
      dotTone: "bg-violet animate-pulse",
    },
    analyzing: {
      label: m.sampleList.statusAnalyzing,
      tone: "text-violet",
      dotTone: "bg-violet animate-pulse",
    },
    done: {
      label: m.sampleList.statusDone,
      tone: "text-teal",
      dotTone: "bg-teal",
    },
    error: {
      label: m.sampleList.statusError,
      tone: "text-red-600",
      dotTone: "bg-red-500",
    },
  };

  if (samples.length === 0) {
    return (
      <p className="mt-4 text-sm italic text-ink/40">{m.sampleList.empty}</p>
    );
  }

  return (
    <ul className="mt-2 space-y-2">
      <AnimatePresence initial={false}>
        {samples.map((s) => {
          const status = STATUS_COPY[s.status];
          return (
            <motion.li
              key={s.id}
              layout
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.97 }}
              transition={{ duration: 0.25, ease: "easeOut" }}
              className="flex items-center gap-3 rounded-xl border border-ink/10 bg-white/60 px-4 py-3 shadow-soft"
            >
              <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-ink/5 text-ink/55">
                <FileText className="size-5" strokeWidth={1.6} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-ink">
                  {s.original_filename}
                </p>
                <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-ink/45">
                  <span className={`flex items-center gap-1.5 ${status.tone}`}>
                    <span
                      className={`inline-block size-1.5 rounded-full ${status.dotTone}`}
                    />
                    {status.label}
                  </span>
                  {s.page_count > 0 ? (
                    <span>· {m.sampleList.pageCount(s.page_count)}</span>
                  ) : null}
                  <span>· {formatDateTime(s.created_at, locale)}</span>
                </div>
                {s.error ? (
                  <p className="mt-1 truncate text-xs text-red-600">
                    {s.error}
                  </p>
                ) : null}
              </div>
              <button
                type="button"
                onClick={() => onDelete(s.id)}
                disabled={pendingDelete === s.id}
                className="shrink-0 text-xs uppercase tracking-wider text-ink/40 transition hover:text-red-600 disabled:opacity-40"
              >
                {pendingDelete === s.id
                  ? m.sampleList.removing
                  : m.sampleList.remove}
              </button>
            </motion.li>
          );
        })}
      </AnimatePresence>
    </ul>
  );
}
