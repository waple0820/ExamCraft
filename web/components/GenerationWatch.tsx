"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { useI18n } from "@/components/I18nProvider";
import {
  backendUrl,
  type ChatMessage,
  type ExamSpec,
  type Generation,
  type ProblemFigure,
} from "@/lib/api";
import { formatDateTime } from "@/lib/format";

import { ExamView } from "@/components/ExamView";
import { ReviseChat } from "@/components/ReviseChat";

function applyFigureUpdate(
  spec: ExamSpec | null,
  problemId: number,
  patch: Partial<Extract<ProblemFigure, { needed: true }>>,
): ExamSpec | null {
  if (!spec?.sections) return spec;
  let touched = false;
  const sections = spec.sections.map((section) => {
    if (!section.problems) return section;
    const problems = section.problems.map((p) => {
      if (p.id !== problemId) return p;
      const fig =
        p.figure && (p.figure as { needed?: boolean }).needed
          ? (p.figure as Extract<ProblemFigure, { needed: true }>)
          : null;
      if (!fig) return p;
      touched = true;
      return { ...p, figure: { ...fig, ...patch } };
    });
    return { ...section, problems };
  });
  return touched ? { ...spec, sections } : spec;
}

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

  // Subscribe to SSE while the job is in flight. We don't surface the
  // internal pipeline names — progress comes from spec + figure events.
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

    es.addEventListener("figure_ready", (ev) => {
      try {
        const data = JSON.parse((ev as MessageEvent).data);
        setJob((j) => ({
          ...j,
          spec: applyFigureUpdate(j.spec, data.problem_id, {
            status: "done",
            image_url: `${data.image_url}?t=${Date.now()}`,
            error: null,
          }),
          progress_pct:
            typeof data.done === "number" && typeof data.total === "number"
              ? Math.min(1, 0.3 + 0.65 * (data.done / Math.max(1, data.total)))
              : j.progress_pct,
        }));
      } catch {
        /* ignore */
      }
    });

    es.addEventListener("figure_error", (ev) => {
      try {
        const data = JSON.parse((ev as MessageEvent).data);
        setJob((j) => ({
          ...j,
          spec: applyFigureUpdate(j.spec, data.problem_id, {
            status: "error",
            error: data.message ?? "render failed",
          }),
        }));
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

  const figureProgress = useMemo(() => {
    let total = 0;
    let done = 0;
    for (const s of job.spec?.sections ?? []) {
      for (const p of s.problems ?? []) {
        const fig = p.figure;
        if (!fig?.needed) continue;
        total += 1;
        if (
          (fig as Extract<ProblemFigure, { needed: true }>).status === "done"
        )
          done += 1;
      }
    }
    return { total, done };
  }, [job.spec]);

  // Step counter: total = 1 (出题/spec) + 1 per needed figure.
  // currentDone = 1 if spec exists else 0, plus figures already rendered.
  const stepProgress = useMemo(() => {
    const specDone = job.spec ? 1 : 0;
    const total = 1 + figureProgress.total; // unknown until spec arrives, but 1 is the floor
    const done = specDone + figureProgress.done;
    return { total, done };
  }, [job.spec, figureProgress]);

  const liveStatus = useMemo(() => {
    if (job.status !== "running" && job.status !== "queued") return null;
    if (!job.spec) {
      // Total still unknown; just "出题中…"
      return m.generation.livePreparing;
    }
    if (figureProgress.total === 0) return m.generation.liveFinishing;
    if (figureProgress.done >= figureProgress.total)
      return m.generation.liveFinishing;
    return m.generation.liveRenderingFigures(
      stepProgress.done,
      stepProgress.total,
      figureProgress.done,
      figureProgress.total,
    );
  }, [job, figureProgress, stepProgress, m]);

  const statusLabels: Record<Generation["status"], string> = {
    queued: m.generation.statusQueued,
    running: m.generation.statusRunning,
    done: m.generation.statusDone,
    failed: m.generation.statusFailed,
  };

  return (
    <div className="space-y-12">
      <header data-no-print>
        <p className="text-xs uppercase tracking-[0.18em] text-ink/45">
          {m.generation.eyebrow}
        </p>
        <h1 className="mt-3 font-display text-4xl tracking-tight">
          {job.spec?.title || m.generation.placeholderTitle}
        </h1>
        <div className="mt-6 flex flex-wrap items-center gap-3 text-sm">
          <StatusPill status={job.status} label={statusLabels[job.status]} />
          <span className="text-ink/40">
            {m.generation.started(formatDateTime(job.created_at, locale))}
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

      <ExamView spec={job.spec ?? null} jobId={job.id} />

      <div data-no-print>
        <ReviseChat
          jobId={job.id}
          initialMessages={chat}
          jobStatus={job.status}
        />
      </div>
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
