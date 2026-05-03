"use client";

import { useState } from "react";

import { useI18n } from "@/components/I18nProvider";
import type { ExamSpec } from "@/lib/api";

export function SpecViewer({ spec }: { spec: ExamSpec | null }) {
  const { messages: m } = useI18n();
  const [showAnswers, setShowAnswers] = useState(false);

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
    <section>
      <div className="flex items-baseline justify-between">
        <h2 className="text-xs uppercase tracking-[0.16em] text-ink/45">
          {m.spec.title}
        </h2>
        <button
          type="button"
          onClick={() => setShowAnswers((s) => !s)}
          className={`text-xs uppercase tracking-wider ${
            showAnswers ? "text-violet" : "text-ink/40 hover:text-violet"
          }`}
        >
          {showAnswers ? m.spec.hideAnswers : m.spec.showAnswers}
        </button>
      </div>

      <div className="mt-4 rounded-2xl border border-ink/10 bg-ivory/60 p-6 shadow-soft">
        {meta && Object.keys(meta).length > 0 ? (
          <div className="mb-6 flex flex-wrap gap-x-6 gap-y-1 text-xs uppercase tracking-wider text-ink/45">
            {Object.entries(meta).map(([k, v]) => (
              <span key={k}>
                {k}: <span className="text-ink/70">{String(v)}</span>
              </span>
            ))}
          </div>
        ) : null}

        {sections.length === 0 ? (
          <p className="text-sm italic text-ink/40">{m.spec.empty}</p>
        ) : (
          <ol className="space-y-8">
            {sections.map((s, idx) => (
              <li key={idx}>
                <h3 className="font-display text-xl tracking-tight">
                  {s.name ?? m.spec.section(idx + 1)}
                </h3>
                {s.instructions ? (
                  <p className="mt-1 text-xs italic text-ink/45">
                    {s.instructions}
                  </p>
                ) : null}
                <ol className="mt-3 space-y-3">
                  {(s.problems ?? []).map((p) => (
                    <li
                      key={p.id}
                      className="rounded-xl border border-ink/5 bg-white/40 p-3 text-sm leading-relaxed"
                    >
                      <div className="flex items-start gap-3">
                        <span className="rounded-full bg-ink/5 px-2 py-0.5 text-xs tabular-nums text-ink/60">
                          #{p.id}
                        </span>
                        <div className="flex-1">
                          <p className="text-ink/90">{p.content}</p>
                          {p.choices && p.choices.length > 0 ? (
                            <ul className="mt-2 grid grid-cols-1 gap-1 text-ink/75 sm:grid-cols-2">
                              {p.choices.map((c, i) => (
                                <li key={i}>{c}</li>
                              ))}
                            </ul>
                          ) : null}
                          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-ink/40">
                            {p.knowledge_point ? (
                              <span className="rounded-full bg-violet/10 px-2 py-0.5 text-violet">
                                {p.knowledge_point}
                              </span>
                            ) : null}
                            {typeof p.difficulty === "number" ? (
                              <span>
                                {m.spec.difficulty(
                                  (p.difficulty * 10).toFixed(1),
                                )}
                              </span>
                            ) : null}
                            {typeof p.points === "number" ? (
                              <span>· {m.spec.points(p.points)}</span>
                            ) : null}
                            <span>
                              ·{" "}
                              {m.analysis.problemTypeLabels[p.type] ??
                                m.analysis.problemTypeLabels[
                                  p.type?.toLowerCase()
                                ] ??
                                p.type?.replace(/_/g, " ") ??
                                ""}
                            </span>
                          </div>
                          {showAnswers ? (
                            <p className="mt-2 rounded-lg bg-teal/10 p-2 text-sm text-teal">
                              <span className="text-xs uppercase tracking-wider">
                                {m.spec.answer}
                              </span>
                              {p.answer}
                            </p>
                          ) : null}
                        </div>
                      </div>
                    </li>
                  ))}
                </ol>
              </li>
            ))}
          </ol>
        )}
      </div>

    </section>
  );
}
