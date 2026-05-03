"use client";

import { Loader2, Printer, RefreshCcw } from "lucide-react";
import Image from "next/image";
import { useMemo, useState } from "react";

import { useI18n } from "@/components/I18nProvider";
import { MathText } from "@/components/MathText";
import {
  backendUrl,
  type ExamProblem,
  type ExamSpec,
  type ProblemFigure,
} from "@/lib/api";

const META_LABELS_ZH: Record<string, string> = {
  subject: "学科",
  grade: "年级",
  duration_minutes: "时长(分钟)",
  total_points: "满分",
};

const META_LABELS_EN: Record<string, string> = {
  subject: "Subject",
  grade: "Grade",
  duration_minutes: "Duration (min)",
  total_points: "Total points",
};

export function ExamView({
  spec,
  jobId,
}: {
  spec: ExamSpec | null;
  jobId: string;
}) {
  const { messages: m, locale } = useI18n();
  const [showAnswers, setShowAnswers] = useState(false);
  const metaLabels = locale === "zh" ? META_LABELS_ZH : META_LABELS_EN;

  const figureStats = useMemo(() => {
    if (!spec?.sections) return { total: 0, done: 0, error: 0, queued: 0 };
    let total = 0;
    let done = 0;
    let error = 0;
    let queued = 0;
    for (const s of spec.sections) {
      for (const p of s.problems ?? []) {
        const fig = p.figure;
        if (!fig?.needed) continue;
        total += 1;
        const st = (fig as Extract<ProblemFigure, { needed: true }>).status;
        if (st === "done") done += 1;
        else if (st === "error") error += 1;
        else queued += 1;
      }
    }
    return { total, done, error, queued };
  }, [spec]);

  if (!spec) {
    return (
      <section>
        <h2 className="text-xs uppercase tracking-[0.16em] text-ink/45">
          {m.spec.placeholderEyebrow}
        </h2>
        <p className="mt-2 text-sm italic text-ink/40">{m.spec.placeholder}</p>
      </section>
    );
  }

  const meta = (spec.meta ?? {}) as Record<string, unknown>;
  const sections = spec.sections ?? [];

  return (
    <section className="space-y-4">
      <div
        className="flex items-baseline justify-between gap-3"
        data-no-print
      >
        <h2 className="text-xs uppercase tracking-[0.16em] text-ink/45">
          {m.exam.eyebrow}
          {figureStats.total > 0 && figureStats.queued + figureStats.error > 0 ? (
            <span className="ml-2 text-violet">
              · {m.exam.figuresProgress(figureStats.done, figureStats.total)}
            </span>
          ) : null}
        </h2>
        <div className="flex items-center gap-3 text-xs uppercase tracking-wider text-ink/40">
          <button
            type="button"
            onClick={() => setShowAnswers((s) => !s)}
            className={
              showAnswers
                ? "text-violet"
                : "text-ink/40 hover:text-violet"
            }
          >
            {showAnswers ? m.spec.hideAnswers : m.spec.showAnswers}
          </button>
          <button
            type="button"
            onClick={() => window.print()}
            className="flex items-center gap-1 text-ink/40 hover:text-violet"
          >
            <Printer className="size-3.5" /> {m.exam.print}
          </button>
        </div>
      </div>

      <article
        data-print-area
        className="space-y-10 rounded-2xl border border-ink/10 bg-ivory/60 p-8 shadow-soft print:p-0"
      >
        <header className="space-y-3 text-center">
          <h1 className="font-display text-3xl tracking-tight">
            {spec.title}
          </h1>
          {Object.keys(meta).length > 0 ? (
            <div className="flex flex-wrap justify-center gap-x-6 gap-y-1 text-xs uppercase tracking-wider text-ink/55">
              {Object.entries(meta).map(([k, v]) => (
                <span key={k}>
                  {metaLabels[k] ?? k.replace(/_/g, " ")}:{" "}
                  <span className="text-ink/80">{String(v)}</span>
                </span>
              ))}
            </div>
          ) : null}
        </header>

        {sections.length === 0 ? (
          <p className="text-sm italic text-ink/40">{m.spec.empty}</p>
        ) : (
          <div className="space-y-10">
            {sections.map((section, sidx) => (
              <section key={sidx} className="space-y-4">
                <div>
                  <h3 className="font-display text-xl tracking-tight">
                    {section.name ?? m.spec.section(sidx + 1)}
                  </h3>
                  {section.instructions ? (
                    <p className="mt-1 text-sm italic text-ink/55">
                      {section.instructions}
                    </p>
                  ) : null}
                </div>
                <ol className="space-y-5">
                  {(section.problems ?? []).map((p) => (
                    <ProblemCard
                      key={p.id}
                      problem={p}
                      jobId={jobId}
                      showAnswer={showAnswers}
                    />
                  ))}
                </ol>
              </section>
            ))}
          </div>
        )}
      </article>
    </section>
  );
}

function ProblemCard({
  problem,
  jobId,
  showAnswer,
}: {
  problem: ExamProblem;
  jobId: string;
  showAnswer: boolean;
}) {
  const { messages: m } = useI18n();
  const typeLabel =
    m.analysis.problemTypeLabels[problem.type] ??
    m.analysis.problemTypeLabels[problem.type?.toLowerCase()] ??
    problem.type?.replace(/_/g, " ") ??
    "";

  return (
    <li className="problem-card rounded-xl border border-ink/5 bg-white/40 p-4 leading-relaxed">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 shrink-0 rounded-full bg-ink/5 px-2 py-0.5 text-xs tabular-nums text-ink/60">
          #{problem.id}
        </span>
        <div className="flex-1 space-y-3">
          <div
            className="flex flex-wrap items-center gap-2 text-xs text-ink/45"
            data-no-print
          >
            {typeLabel ? <span>{typeLabel}</span> : null}
            {problem.knowledge_point ? (
              <span className="rounded-full bg-violet/10 px-2 py-0.5 text-violet">
                {problem.knowledge_point}
              </span>
            ) : null}
            {typeof problem.difficulty === "number" ? (
              <span>{m.spec.difficulty((problem.difficulty * 10).toFixed(1))}</span>
            ) : null}
            {typeof problem.points === "number" ? (
              <span>· {m.spec.points(problem.points)}</span>
            ) : null}
          </div>

          <MathText className="text-base text-ink/90">
            {problem.content}
          </MathText>

          {problem.choices && problem.choices.length > 0 ? (
            <ul className="grid grid-cols-1 gap-1 text-ink/80 sm:grid-cols-2">
              {problem.choices.map((c, i) => (
                <li key={i}>
                  <MathText>{c}</MathText>
                </li>
              ))}
            </ul>
          ) : null}

          {problem.figure?.needed ? (
            <FigureSlot problem={problem} jobId={jobId} />
          ) : null}

          {showAnswer ? (
            <p className="rounded-lg bg-teal/10 p-2 text-sm text-teal">
              <span className="text-xs uppercase tracking-wider">
                {m.spec.answer}
              </span>
              <MathText>{problem.answer}</MathText>
            </p>
          ) : null}
        </div>
      </div>
    </li>
  );
}

function FigureSlot({
  problem,
  jobId,
}: {
  problem: ExamProblem;
  jobId: string;
}) {
  const { messages: m } = useI18n();
  const fig = problem.figure as Extract<ProblemFigure, { needed: true }>;
  const status = fig.status ?? "queued";

  // Prefer the URL provided by the server; fall back to the canonical path.
  // The cache-busting suffix on done makes hot-swapped figures show up after
  // a chat revision.
  const url =
    status === "done"
      ? backendUrl(
          fig.image_url ??
            `/api/generations/${jobId}/problems/${problem.id}/figure`,
        )
      : null;

  return (
    <figure className="mt-2 flex flex-col items-center gap-2 rounded-lg border border-ink/5 bg-white/60 p-3">
      {status === "done" && url ? (
        <div className="relative aspect-square w-full max-w-xs overflow-hidden rounded-md bg-white">
          <Image
            src={url}
            alt={`figure for problem ${problem.id}`}
            fill
            className="object-contain"
            unoptimized
            sizes="(max-width: 768px) 80vw, 320px"
          />
        </div>
      ) : status === "error" ? (
        <div
          className="flex aspect-square w-full max-w-xs flex-col items-center justify-center gap-1 rounded-md border border-dashed border-red-300 bg-red-50/40 p-4 text-center"
          data-no-print
        >
          <RefreshCcw className="size-5 text-red-500" />
          <p className="text-xs text-red-600">{m.exam.figureFailed}</p>
          <p className="text-[11px] text-ink/45">{m.exam.figureRetryHint}</p>
        </div>
      ) : (
        <div
          className="flex aspect-square w-full max-w-xs flex-col items-center justify-center gap-2 rounded-md border border-dashed border-ink/15 bg-ink/5"
          data-no-print
        >
          <Loader2 className="size-5 animate-spin text-violet" />
          <p className="text-xs text-ink/55">{m.exam.figureRendering}</p>
        </div>
      )}
    </figure>
  );
}
