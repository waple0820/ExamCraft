"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import type { Sample, SampleStatus } from "@/lib/api";
import { backendUrl } from "@/lib/api";
import { clientDeleteSample } from "@/lib/client";

const STATUS_COPY: Record<SampleStatus, { label: string; tone: string }> = {
  uploaded: { label: "queued", tone: "text-ink/45" },
  extracting: { label: "extracting pages", tone: "text-violet" },
  analyzing: { label: "analyzing", tone: "text-violet" },
  done: { label: "ready", tone: "text-teal" },
  error: { label: "error", tone: "text-red-600" },
};

export function SampleList({
  bankId,
  initialSamples,
}: {
  bankId: string;
  initialSamples: Sample[];
}) {
  const router = useRouter();
  const [samples, setSamples] = useState<Sample[]>(initialSamples);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);

  const anyInFlight = useMemo(
    () => samples.some((s) => s.status === "uploaded" || s.status === "extracting" || s.status === "analyzing"),
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
        const stillRunning = fresh.some(
          (s) => s.status === "uploaded" || s.status === "extracting" || s.status === "analyzing",
        );
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

  if (samples.length === 0) {
    return (
      <p className="mt-6 text-sm italic text-ink/40">
        No samples yet. Upload one above.
      </p>
    );
  }

  return (
    <ul className="mt-6 divide-y divide-ink/5">
      {samples.map((s) => {
        const status = STATUS_COPY[s.status];
        return (
          <li
            key={s.id}
            className="flex items-center justify-between gap-4 py-4"
          >
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{s.original_filename}</p>
              <div className="mt-1 flex items-center gap-3 text-xs text-ink/45">
                <span className={status.tone}>{status.label}</span>
                {s.page_count > 0 ? <span>· {s.page_count} pages</span> : null}
                <span>· {new Date(s.created_at).toLocaleString()}</span>
              </div>
              {s.error ? (
                <p className="mt-1 truncate text-xs text-red-600">{s.error}</p>
              ) : null}
            </div>
            <button
              type="button"
              onClick={() => onDelete(s.id)}
              disabled={pendingDelete === s.id}
              className="text-xs uppercase tracking-wider text-ink/40 hover:text-red-600 disabled:opacity-40"
            >
              {pendingDelete === s.id ? "…" : "remove"}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
