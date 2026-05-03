"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { useI18n } from "@/components/I18nProvider";
import { clientCreateBank } from "@/lib/client";

export function CreateBankCard() {
  const router = useRouter();
  const { messages: m } = useI18n();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await clientCreateBank({
        name: name.trim(),
        description: description.trim() || undefined,
      });
      setName("");
      setDescription("");
      setOpen(false);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="group flex min-h-[180px] flex-col items-center justify-center rounded-2xl border-2 border-dashed border-ink/15 bg-white/30 p-6 text-center transition hover:border-violet/50 hover:bg-white/60"
      >
        <span className="font-display text-3xl text-ink/30 transition group-hover:text-violet">
          {m.dashboard.newBankPlus}
        </span>
        <span className="mt-2 text-sm text-ink/55 transition group-hover:text-violet">
          {m.dashboard.newBank}
        </span>
      </button>
    );
  }

  return (
    <form
      onSubmit={onSubmit}
      className="rounded-2xl border border-violet/30 bg-white/80 p-6 shadow-soft"
    >
      <h2 className="font-display text-xl tracking-tight">{m.newBank.title}</h2>
      <label className="mt-4 block">
        <span className="text-xs uppercase tracking-wider text-ink/55">
          {m.newBank.nameLabel}
        </span>
        <input
          autoFocus
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={m.newBank.namePlaceholder}
          maxLength={120}
          required
          className="mt-1.5 w-full rounded-lg border border-ink/15 bg-white px-3 py-2 outline-none focus:border-violet focus:ring-2 focus:ring-violet/30"
        />
      </label>
      <label className="mt-3 block">
        <span className="text-xs uppercase tracking-wider text-ink/55">
          {m.newBank.descLabel}
        </span>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder={m.newBank.descPlaceholder}
          maxLength={500}
          rows={2}
          className="mt-1.5 w-full resize-none rounded-lg border border-ink/15 bg-white px-3 py-2 outline-none focus:border-violet focus:ring-2 focus:ring-violet/30"
        />
      </label>
      {error ? <p className="mt-2 text-sm text-red-600">{error}</p> : null}
      <div className="mt-4 flex items-center gap-2">
        <button
          type="submit"
          disabled={busy || !name.trim()}
          className="rounded-full bg-ink px-4 py-2 text-sm font-medium text-ivory transition hover:bg-violet disabled:opacity-40"
        >
          {busy ? m.newBank.creating : m.newBank.create}
        </button>
        <button
          type="button"
          onClick={() => {
            setOpen(false);
            setError(null);
          }}
          disabled={busy}
          className="text-sm text-ink/55 hover:text-ink"
        >
          {m.common.cancel}
        </button>
      </div>
    </form>
  );
}
