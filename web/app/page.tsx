import Link from "next/link";

import { apiHealth } from "@/lib/api";

export default async function HomePage() {
  let health: { status: string; version: string; model: string } | null = null;
  let healthError: string | null = null;
  try {
    health = await apiHealth();
  } catch (err) {
    healthError = err instanceof Error ? err.message : String(err);
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-24">
      <p className="text-xs uppercase tracking-[0.18em] text-ink/50">ExamCraft</p>
      <h1 className="mt-6 font-display text-5xl leading-tight tracking-tight md:text-6xl">
        Sample exams in,
        <br />
        <span className="text-violet">fresh ones out.</span>
      </h1>
      <p className="mt-6 max-w-xl text-lg leading-relaxed text-ink/70">
        Drop your teachers&apos; exam papers into a question bank. ExamCraft
        learns the knowledge points and the visual feel, then generates new
        practice exams in the same style — page-by-page, on demand.
      </p>

      <div className="mt-12 flex items-center gap-4">
        <Link
          href="/login"
          className="rounded-full bg-ink px-6 py-3 text-sm font-medium text-ivory shadow-soft transition hover:bg-violet"
        >
          Sign in
        </Link>
        <span className="text-sm text-ink/50">No password required.</span>
      </div>

      <div className="mt-24 rounded-2xl border border-ink/10 bg-white/60 p-6 text-sm shadow-soft backdrop-blur">
        <p className="mb-2 font-medium">Backend status</p>
        {health ? (
          <pre className="whitespace-pre-wrap text-xs text-ink/70">
{JSON.stringify(health, null, 2)}
          </pre>
        ) : (
          <p className="text-xs text-ink/50">
            Backend unreachable — start it with{" "}
            <code className="rounded bg-ink/5 px-1.5 py-0.5">make backend</code>.{" "}
            ({healthError})
          </p>
        )}
      </div>
    </div>
  );
}
