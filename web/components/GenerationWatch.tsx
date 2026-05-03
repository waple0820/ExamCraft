"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { useI18n } from "@/components/I18nProvider";
import { backendUrl, type ChatMessage, type Generation } from "@/lib/api";

import { PageGallery } from "@/components/PageGallery";
import { ReviseChat } from "@/components/ReviseChat";
import { SpecViewer } from "@/components/SpecViewer";

export function GenerationWatch({
  initial,
  initialChat,
}: {
  initial: Generation;
  initialChat: ChatMessage[];
}) {
  const router = useRouter();
  const { messages: m, locale } = useI18n();
  const [job, setJob] = useState<Generation>(initial);
  const [chat, setChat] = useState<ChatMessage[]>(initialChat);

  // Subscribe to SSE while the job is in flight. We deliberately do NOT
  // expose internal step events to the user — the progress bar, page
  // gallery and spec viewer give plenty of visible feedback without
  // leaking generation-pipeline internals.
  useEffect(() => {
    if (job.status === "done" || job.status === "failed") return;
    const url = backendUrl(`/api/generations/${job.id}/events`);
    const es = new EventSource(url, { withCredentials: true });

    es.addEventListener("spec_ready", (ev) => {
      try {
        const data = JSON.parse((ev as MessageEvent).data);
        setJob((j) => ({ ...j, spec: data.spec }));
      } catch {
        /* ignore */
      }
    });

    es.addEventListener("page_ready", (ev) => {
      try {
        const data = JSON.parse((ev as MessageEvent).data);
        setJob((j) => {
          const idx = j.pages.findIndex((p) => p.page_number === data.page);
          const updated = {
            page_number: data.page,
            status: "done" as const,
            image_url: data.image_url,
            error: null,
          };
          const pages =
            idx >= 0
              ? j.pages.map((p, i) => (i === idx ? updated : p))
              : [...j.pages, updated].sort(
                  (a, b) => a.page_number - b.page_number,
                );
          return { ...j, pages, progress_pct: data.done / data.total };
        });
      } catch {
        /* ignore */
      }
    });

    es.addEventListener("page_error", (ev) => {
      try {
        const data = JSON.parse((ev as MessageEvent).data);
        setJob((j) => {
          const idx = j.pages.findIndex((p) => p.page_number === data.page);
          const updated = {
            page_number: data.page,
            status: "error" as const,
            image_url: null,
            error: data.message ?? "render failed",
          };
          const pages =
            idx >= 0
              ? j.pages.map((p, i) => (i === idx ? updated : p))
              : [...j.pages, updated].sort(
                  (a, b) => a.page_number - b.page_number,
                );
          return { ...j, pages };
        });
      } catch {
        /* ignore */
      }
    });

    es.addEventListener("chat", (ev) => {
      try {
        const data = JSON.parse((ev as MessageEvent).data);
        if (data.role === "assistant") {
          setChat((c) => [
            ...c,
            {
              id: `assistant-${Date.now()}`,
              role: "assistant",
              content: data.message,
              created_at: new Date().toISOString(),
            },
          ]);
        }
      } catch {
        /* ignore */
      }
    });

    es.addEventListener("done", () => {
      setJob((j) => ({ ...j, status: "done", progress_pct: 1 }));
      es.close();
      router.refresh();
    });

    return () => {
      es.close();
    };
  }, [job.id, job.status, router]);

  const pct = useMemo(
    () => Math.max(0, Math.min(100, Math.round(job.progress_pct * 100))),
    [job.progress_pct],
  );

  const liveStatus = useMemo(() => {
    if (job.status !== "running" && job.status !== "queued") return null;
    const total = job.pages.length;
    const done = job.pages.filter(
      (p) => p.image_url || p.status === "done",
    ).length;
    if (total === 0) {
      return job.spec ? m.generation.liveLayingOut : m.generation.livePreparing;
    }
    if (done >= total) return m.generation.liveFinishing;
    return m.generation.liveRendering(done, total);
  }, [job, m]);

  const dateLocale = locale === "zh" ? "zh-CN" : "en-US";
  const statusLabels: Record<Generation["status"], string> = {
    queued: m.generation.statusQueued,
    running: m.generation.statusRunning,
    done: m.generation.statusDone,
    failed: m.generation.statusFailed,
  };

  return (
    <div className="space-y-12">
      <header>
        <p className="text-xs uppercase tracking-[0.18em] text-ink/45">
          {m.generation.eyebrow}
        </p>
        <h1 className="mt-3 font-display text-4xl tracking-tight">
          {job.spec?.title || m.generation.placeholderTitle}
        </h1>
        <div className="mt-6 flex flex-wrap items-center gap-3 text-sm">
          <StatusPill status={job.status} label={statusLabels[job.status]} />
          <span className="text-ink/40">
            {m.generation.started(
              new Date(job.created_at).toLocaleString(dateLocale),
            )}
          </span>
        </div>
        {job.status !== "done" && job.status !== "failed" ? (
          <div className="mt-4 space-y-2">
            <div className="h-1 w-full overflow-hidden rounded-full bg-ink/5">
              <div
                className="h-full bg-violet transition-all duration-700 ease-out"
                style={{ width: `${pct}%` }}
              />
            </div>
            {liveStatus ? (
              <p className="text-sm text-violet">{liveStatus}</p>
            ) : null}
          </div>
        ) : null}
        {job.error ? (
          <p className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-600">
            {job.error}
          </p>
        ) : null}
      </header>

      <PageGallery pages={job.pages} />

      <SpecViewer spec={job.spec ?? null} />

      <ReviseChat
        jobId={job.id}
        initialMessages={chat}
        jobStatus={job.status}
      />
    </div>
  );
}

function StatusPill({
  status,
  label,
}: {
  status: Generation["status"];
  label: string;
}) {
  const tone = {
    queued: "bg-ink/10 text-ink/60",
    running: "bg-violet/10 text-violet",
    done: "bg-teal/10 text-teal",
    failed: "bg-red-100 text-red-600",
  }[status];
  return (
    <span
      className={`rounded-full px-3 py-1 text-xs uppercase tracking-wider ${tone}`}
    >
      {label}
    </span>
  );
}
