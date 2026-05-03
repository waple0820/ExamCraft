import Link from "next/link";
import { notFound } from "next/navigation";

import { getBank } from "@/lib/server";

export const dynamic = "force-dynamic";

export default async function BankDetail({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const bank = await getBank(id);
  if (!bank) notFound();

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

      <section className="rounded-2xl border border-ink/10 bg-white/60 p-8 shadow-soft">
        <h2 className="font-display text-2xl tracking-tight">Sample exams</h2>
        <p className="mt-2 text-sm text-ink/55">
          Upload .docx or .pdf files of teachers&apos; sample exams. ExamCraft
          will analyze each page and learn the bank&apos;s style.
        </p>
        <p className="mt-6 text-sm italic text-ink/40">
          Upload UI lands in M3 — coming next.
        </p>
      </section>

      <section className="rounded-2xl border border-ink/10 bg-white/60 p-8 shadow-soft">
        <h2 className="font-display text-2xl tracking-tight">Generate</h2>
        <p className="mt-2 text-sm text-ink/55">
          Once samples are analyzed, you&apos;ll be able to generate brand-new
          exams in this bank&apos;s style.
        </p>
        <p className="mt-6 text-sm italic text-ink/40">
          Generation lands in M4.
        </p>
      </section>
    </div>
  );
}
