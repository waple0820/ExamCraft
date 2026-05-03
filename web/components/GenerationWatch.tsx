"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { backendUrl, type ChatMessage, type Generation } from "@/lib/api";

import { PageGallery } from "@/components/PageGallery";
import { ReviseChat } from "@/components/ReviseChat";
import { SpecViewer } from "@/components/SpecViewer";

const STEP_LABELS: Record<string, string> = {
  spec: "Building exam spec",
  layout: "Planning page layout",
  render: "Rendering pages",
};

type LogEntry = {
  ts: string;
  message: string;
  tone: "info" | "ok" | "err";
};

export function GenerationWatch({
  initial,
  initialChat,
}: {
  initial: Generation;
  initialChat: ChatMessage[];
}) {
  const router = useRouter();
  const [job, setJob] = useState<Generation>(initial);
  const [log, setLog] = useState<LogEntry[]>([]);
  const [chat, setChat] = useState<ChatMessage[]>(initialChat);

  // Subscribe to SSE while the job is in flight.
  useEffect(() => {
    if (job.status === "done" || job.status === "failed") return;
    const url = backendUrl(`/api/generations/${job.id}/events`);
    const es = new EventSource(url, { withCredentials: true });

    const append = (message: string, tone: LogEntry["tone"] = "info") => {
      setLog((prev) => [
        ...prev,
        { ts: new Date().toLocaleTimeString(), message, tone },
      ]);
    };

    es.addEventListener("step", (ev) => {
      try {
        const data = JSON.parse((ev as MessageEvent).data);
        const label = STEP_LABELS[data.step] ?? data.step;
        append(label);
      } catch {
        /* ignore */
      }
    });

    es.addEventListener("spec_ready", (ev) => {
      try {
        const data = JSON.parse((ev as MessageEvent).data);
        setJob((j) => ({ ...j, spec: data.spec }));
        append("Spec ready", "ok");
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
              : [...j.pages, updated].sort((a, b) => a.page_number - b.page_number);
          return { ...j, pages, progress_pct: data.done / data.total };
        });
        append(`Page ${data.page} of ${data.total} ready`, "ok");
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
          append(`Editor: ${data.message}`, "ok");
        }
      } catch {
        /* ignore */
      }
    });

    es.addEventListener("done", () => {
      append("All pages ready", "ok");
      setJob((j) => ({ ...j, status: "done", progress_pct: 1 }));
      es.close();
      router.refresh();
    });

    es.addEventListener("error", (ev) => {
      try {
        const data = JSON.parse((ev as MessageEvent).data);
        append(data.message ?? "error", "err");
      } catch {
        // Browser EventSource fires "error" on disconnect too — tolerate it.
      }
    });

    return () => {
      es.close();
    };
  }, [job.id, job.status, router]);

  const pct = useMemo(
    () => Math.max(0, Math.min(100, Math.round(job.progress_pct * 100))),
    [job.progress_pct],
  );

  return (
    <div className="space-y-12">
      <header>
        <p className="text-xs uppercase tracking-[0.18em] text-ink/45">
          Generation
        </p>
        <h1 className="mt-3 font-display text-4xl tracking-tight">
          {job.spec?.title || "(building exam…)"}
        </h1>
        <div className="mt-6 flex flex-wrap items-center gap-3 text-sm">
          <StatusPill status={job.status} />
          <span className="text-ink/40">
            started {new Date(job.created_at).toLocaleString()}
          </span>
          {job.current_step ? (
            <span className="text-ink/55">· {job.current_step}</span>
          ) : null}
        </div>
        {job.status !== "done" && job.status !== "failed" ? (
          <div className="mt-4 h-1 w-full overflow-hidden rounded-full bg-ink/5">
            <div
              className="h-full bg-violet transition-all duration-700 ease-out"
              style={{ width: `${pct}%` }}
            />
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

      <section>
        <h2 className="text-xs uppercase tracking-[0.16em] text-ink/45">
          Activity
        </h2>
        <ul className="mt-3 space-y-1 text-xs">
          {log.length === 0 ? (
            <li className="italic text-ink/40">
              {job.status === "done"
                ? "(this run already completed; resubscribe events on refresh)"
                : "Waiting for events…"}
            </li>
          ) : (
            log.map((l, i) => (
              <li
                key={i}
                className={
                  l.tone === "ok"
                    ? "text-teal"
                    : l.tone === "err"
                      ? "text-red-600"
                      : "text-ink/55"
                }
              >
                <span className="font-mono text-ink/30">{l.ts}</span>{" "}
                {l.message}
              </li>
            ))
          )}
        </ul>
      </section>
    </div>
  );
}

function StatusPill({ status }: { status: Generation["status"] }) {
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
      {status}
    </span>
  );
}
