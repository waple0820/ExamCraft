import Link from "next/link";
import { notFound } from "next/navigation";

import { AnalysisPanel } from "@/components/AnalysisPanel";
import { GenerateButton } from "@/components/GenerateButton";
import { GenerationsList } from "@/components/GenerationsList";
import { SampleList } from "@/components/SampleList";
import { SampleUploader } from "@/components/SampleUploader";
import {
  getBank,
  getBankAnalysis,
  listGenerations,
  listSamples,
} from "@/lib/server";

export const dynamic = "force-dynamic";

export default async function BankDetail({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const bank = await getBank(id);
  if (!bank) notFound();

  const [samples, analysis, generations] = await Promise.all([
    listSamples(id),
    getBankAnalysis(id),
    listGenerations(id),
  ]);
  const ready = analysis.status === "done";

  return (
    <div className="space-y-12">
      <div>
        <Link href="/" className="text-sm text-ink/50 hover:text-violet">
          ← Back to shelf
        </Link>
        <h1 className="mt-4 font-display text-5xl tracking-tight">{bank.name}</h1>
        {bank.description ? (
          <p className="mt-3 max-w-2xl text-ink/60">{bank.description}</p>
        ) : null}
      </div>

      <section className="space-y-4 rounded-2xl border border-ink/10 bg-white/60 p-8 shadow-soft">
        <div className="flex items-baseline justify-between">
          <h2 className="font-display text-2xl tracking-tight">Sample exams</h2>
          <span className="text-xs uppercase tracking-wider text-ink/40">
            {samples.length} uploaded
          </span>
        </div>
        <p className="text-sm text-ink/55">
          Drop teachers&apos; exam papers here. ExamCraft renders each page,
          calls a vision model on every page, then aggregates into a bank
          profile that future generations will use as a style reference.
        </p>
        <SampleUploader bankId={id} />
        <SampleList bankId={id} initialSamples={samples} />
      </section>

      <section className="space-y-2 rounded-2xl border border-ink/10 bg-white/60 p-8 shadow-soft">
        <div className="flex items-baseline justify-between">
          <h2 className="font-display text-2xl tracking-tight">Bank profile</h2>
          <span className="text-xs uppercase tracking-wider text-ink/40">
            aggregated style + topics
          </span>
        </div>
        <AnalysisPanel bankId={id} initial={analysis} />
      </section>

      <section className="space-y-4 rounded-2xl border border-ink/10 bg-white/60 p-8 shadow-soft">
        <div className="flex items-baseline justify-between">
          <h2 className="font-display text-2xl tracking-tight">Generate</h2>
          <span className="text-xs uppercase tracking-wider text-ink/40">
            new exam in this bank&apos;s style
          </span>
        </div>
        <p className="text-sm text-ink/55">
          Builds a fresh exam spec, plans page layout, then renders each page
          via gpt-image-2. The structured spec (the printable, editable source
          of truth) and the stylized page images live side-by-side.
        </p>
        <GenerateButton
          bankId={id}
          ready={ready}
          hint={
            ready
              ? undefined
              : "Upload at least one sample and wait for the bank profile to aggregate before generating."
          }
        />
        <GenerationsList items={generations} />
      </section>
    </div>
  );
}
