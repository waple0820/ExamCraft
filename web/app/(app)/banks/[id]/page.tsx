import Link from "next/link";
import { notFound } from "next/navigation";

import { AnalysisPanel } from "@/components/AnalysisPanel";
import { GenerateButton } from "@/components/GenerateButton";
import { GenerationsList } from "@/components/GenerationsList";
import { SampleList } from "@/components/SampleList";
import { SampleUploader } from "@/components/SampleUploader";
import { getMessages } from "@/lib/i18n/server";
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

  const [samples, analysis, generations, { messages: m }] = await Promise.all([
    listSamples(id),
    getBankAnalysis(id),
    listGenerations(id),
    getMessages(),
  ]);
  const ready = analysis.status === "done";

  return (
    <div className="space-y-12">
      <div>
        <Link href="/" className="text-sm text-ink/50 hover:text-violet">
          {m.bankDetail.back}
        </Link>
        <h1 className="mt-4 font-display text-5xl tracking-tight">{bank.name}</h1>
        {bank.description ? (
          <p className="mt-3 max-w-2xl text-ink/60">{bank.description}</p>
        ) : null}
      </div>

      <section className="space-y-4 rounded-2xl border border-ink/10 bg-white/60 p-8 shadow-soft">
        <div className="flex items-baseline justify-between">
          <h2 className="font-display text-2xl tracking-tight">
            {m.bankDetail.samplesTitle}
          </h2>
          <span className="text-xs uppercase tracking-wider text-ink/40">
            {m.bankDetail.samplesUploaded(samples.length)}
          </span>
        </div>
        <p className="text-sm text-ink/55">{m.bankDetail.samplesDesc}</p>
        <SampleUploader bankId={id} />
        <SampleList bankId={id} initialSamples={samples} />
      </section>

      <section className="space-y-2 rounded-2xl border border-ink/10 bg-white/60 p-8 shadow-soft">
        <div className="flex items-baseline justify-between">
          <h2 className="font-display text-2xl tracking-tight">
            {m.bankDetail.profileTitle}
          </h2>
          <span className="text-xs uppercase tracking-wider text-ink/40">
            {m.bankDetail.profileSubtitle}
          </span>
        </div>
        <AnalysisPanel bankId={id} initial={analysis} />
      </section>

      <section className="space-y-4 rounded-2xl border border-ink/10 bg-white/60 p-8 shadow-soft">
        <div className="flex items-baseline justify-between">
          <h2 className="font-display text-2xl tracking-tight">
            {m.bankDetail.generateTitle}
          </h2>
          <span className="text-xs uppercase tracking-wider text-ink/40">
            {m.bankDetail.generateSubtitle}
          </span>
        </div>
        <p className="text-sm text-ink/55">{m.bankDetail.generateDesc}</p>
        <GenerateButton bankId={id} ready={ready} />
        <GenerationsList items={generations} />
      </section>
    </div>
  );
}
