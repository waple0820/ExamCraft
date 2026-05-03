"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { useI18n } from "@/components/I18nProvider";
import { clientStartGeneration } from "@/lib/client";

export function GenerateButton({
  bankId,
  ready,
}: {
  bankId: string;
  ready: boolean;
}) {
  const router = useRouter();
  const { messages: m } = useI18n();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onClick() {
    setError(null);
    setBusy(true);
    try {
      const { id } = await clientStartGeneration(bankId);
      router.push(`/generations/${id}` as never);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  return (
    <div>
      <button
        type="button"
        onClick={onClick}
        disabled={!ready || busy}
        className="rounded-full bg-violet px-6 py-3 text-sm font-medium text-ivory shadow-soft transition hover:bg-violet-muted disabled:cursor-not-allowed disabled:bg-ink/15 disabled:text-ink/40 disabled:shadow-none"
      >
        {busy ? m.generate.starting : m.generate.button}
      </button>
      {!ready ? (
        <p className="mt-3 text-sm text-ink/45">{m.generate.needBank}</p>
      ) : null}
      {error ? <p className="mt-2 text-sm text-red-600">{error}</p> : null}
    </div>
  );
}
