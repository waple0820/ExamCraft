"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useI18n } from "@/components/I18nProvider";
import { backendUrl, type BankAnalysis } from "@/lib/api";
import { clientRefreshAnalysis } from "@/lib/client";

export function AnalysisPanel({
  bankId,
  initial,
}: {
  bankId: string;
  initial: BankAnalysis;
}) {
  const router = useRouter();
  const { messages: m } = useI18n();
  const [data, setData] = useState<BankAnalysis>(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setData(initial);
  }, [initial]);

  useEffect(() => {
    if (data.status !== "running") return;
    let alive = true;
    const id = setInterval(async () => {
      try {
        const res = await fetch(backendUrl(`/api/banks/${bankId}/analysis`), {
          credentials: "include",
          cache: "no-store",
        });
        if (!res.ok) return;
        const fresh = (await res.json()) as BankAnalysis;
        if (!alive) return;
        setData(fresh);
        if (fresh.status === "done" || fresh.status === "error") {
          router.refresh();
        }
      } catch {
        /* ignore */
      }
    }, 2000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [data.status, bankId, router]);

  async function refresh() {
    setError(null);
    setBusy(true);
    try {
      await clientRefreshAnalysis(bankId);
      setData((d) => ({ ...d, status: "running", error: null }));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  if (data.sample_count === 0) {
    return (
      <p className="mt-2 text-sm italic text-ink/40">
        {m.analysis.waitingSamples}
      </p>
    );
  }

  if (data.status === "running") {
    return (
      <div className="mt-2">
        <p className="text-sm text-violet">
          {m.analysis.aggregating(data.samples_done, data.sample_count)}
        </p>
        <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-ink/5">
          <div className="h-full w-1/3 animate-pulse bg-violet" />
        </div>
      </div>
    );
  }

  if (data.status === "error") {
    return (
      <div className="mt-2 space-y-3">
        <p className="text-sm text-red-600">
          {m.analysis.aggregateError(data.error ?? "")}
        </p>
        <button
          type="button"
          onClick={refresh}
          disabled={busy}
          className="rounded-full bg-ink px-4 py-2 text-sm font-medium text-ivory hover:bg-violet disabled:opacity-40"
        >
          {busy ? m.analysis.retrying : m.analysis.tryAgain}
        </button>
      </div>
    );
  }

  if (data.status === "idle" || data.analysis === null) {
    return (
      <div className="mt-2 space-y-3">
        <p className="text-sm text-ink/55">
          {data.samples_done > 0
            ? m.analysis.samplesAnalyzed(data.samples_done)
            : m.analysis.sampleWaiting}
        </p>
        {data.samples_done > 0 ? (
          <button
            type="button"
            onClick={refresh}
            disabled={busy}
            className="rounded-full bg-ink px-4 py-2 text-sm font-medium text-ivory hover:bg-violet disabled:opacity-40"
          >
            {busy ? m.analysis.queuing : m.analysis.aggregateNow}
          </button>
        ) : null}
        {error ? <p className="text-sm text-red-600">{error}</p> : null}
      </div>
    );
  }

  // status === "done"
  return (
    <div className="mt-4 space-y-6">
      <div className="flex items-center gap-3">
        <span className="rounded-full bg-teal/10 px-3 py-1 text-xs uppercase tracking-wider text-teal">
          {m.analysis.statusReady}
        </span>
        <span className="text-xs text-ink/45">
          {m.analysis.aggregatedFrom(data.samples_done, data.sample_count)}
        </span>
        <button
          type="button"
          onClick={refresh}
          disabled={busy}
          className="ml-auto text-xs uppercase tracking-wider text-ink/40 hover:text-violet"
        >
          {busy ? m.analysis.reAggregating : m.analysis.reAggregate}
        </button>
      </div>

      <AnalysisRender analysis={data.analysis as Record<string, unknown>} />
    </div>
  );
}

function AnalysisRender({ analysis }: { analysis: Record<string, unknown> }) {
  const { messages: m } = useI18n();
  const summary = typeof analysis.summary === "string" ? analysis.summary : null;
  const style = isRecord(analysis.style_profile) ? analysis.style_profile : null;
  const knowledge = isRecord(analysis.knowledge_point_distribution)
    ? (analysis.knowledge_point_distribution as Record<string, number>)
    : null;
  const problems = isRecord(analysis.problem_type_distribution)
    ? (analysis.problem_type_distribution as Record<string, number>)
    : null;
  const difficulty =
    typeof analysis.difficulty_curve === "string"
      ? analysis.difficulty_curve
      : null;
  const pageCount =
    typeof analysis.typical_page_count === "number"
      ? analysis.typical_page_count
      : null;

  return (
    <div className="space-y-5">
      {summary ? (
        <p className="rounded-xl border border-ink/10 bg-ivory/60 p-4 text-sm leading-relaxed text-ink/80">
          {summary}
        </p>
      ) : null}

      {knowledge ? (
        <Section title={m.analysis.knowledgePoints}>
          <DistBars dist={knowledge} />
        </Section>
      ) : null}

      {problems ? (
        <Section title={m.analysis.problemTypes}>
          <DistBars dist={problems} />
        </Section>
      ) : null}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {style ? (
          <Section title={m.analysis.styleProfile}>
            <KvList obj={style} />
          </Section>
        ) : null}
        <Section title={m.analysis.shape}>
          <ul className="space-y-1 text-sm text-ink/70">
            {pageCount !== null ? (
              <li>{m.analysis.typicalPages(pageCount)}</li>
            ) : null}
            {difficulty ? <li>{m.analysis.difficulty(difficulty)}</li> : null}
          </ul>
        </Section>
      </div>

      <details className="rounded-xl border border-ink/10 bg-white/40 p-3 text-xs">
        <summary className="cursor-pointer text-ink/55">
          {m.analysis.rawJson}
        </summary>
        <pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-[11px] text-ink/65">
          {JSON.stringify(analysis, null, 2)}
        </pre>
      </details>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <h3 className="text-xs uppercase tracking-[0.16em] text-ink/45">{title}</h3>
      <div className="mt-2">{children}</div>
    </div>
  );
}

function DistBars({ dist }: { dist: Record<string, number> }) {
  const entries = Object.entries(dist).sort(([, a], [, b]) => Number(b) - Number(a));
  const max = Math.max(...entries.map(([, v]) => Number(v) || 0), 0.01);
  return (
    <ul className="space-y-1.5">
      {entries.map(([k, v]) => {
        const pct = (Number(v) || 0) / max;
        return (
          <li
            key={k}
            className="grid grid-cols-[1fr,auto] items-center gap-3 text-sm"
          >
            <div>
              <div className="flex items-baseline justify-between">
                <span className="text-ink/80">{k}</span>
                <span className="text-xs tabular-nums text-ink/40">
                  {(Number(v) * 100).toFixed(0)}%
                </span>
              </div>
              <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-ink/5">
                <div
                  className="h-full rounded-full bg-violet"
                  style={{ width: `${pct * 100}%` }}
                />
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function KvList({ obj }: { obj: Record<string, unknown> }) {
  return (
    <dl className="space-y-2 text-sm">
      {Object.entries(obj).map(([k, v]) => (
        <div key={k}>
          <dt className="text-xs uppercase tracking-wider text-ink/40">{k}</dt>
          <dd className="text-ink/80">
            {typeof v === "string" ? v : JSON.stringify(v)}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}
