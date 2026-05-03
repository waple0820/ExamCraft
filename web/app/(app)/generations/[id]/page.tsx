import Link from "next/link";
import { notFound } from "next/navigation";

import { GenerationWatch } from "@/components/GenerationWatch";
import { getMessages } from "@/lib/i18n/server";
import { getGeneration, listChat } from "@/lib/server";

export const dynamic = "force-dynamic";

export default async function GenerationPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const initial = await getGeneration(id);
  if (!initial) notFound();
  const [initialChat, { messages: m }] = await Promise.all([
    listChat(id),
    getMessages(),
  ]);

  return (
    <div className="space-y-8">
      <Link
        href={`/banks/${initial.bank_id}` as never}
        className="text-sm text-ink/50 hover:text-violet"
      >
        {m.generation.backToBank}
      </Link>
      <GenerationWatch initial={initial} initialChat={initialChat} />
    </div>
  );
}
