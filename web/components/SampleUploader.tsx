"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { clientUploadSample } from "@/lib/client";

const ACCEPT = ".pdf,.docx,.doc,.odt,.rtf";

export function SampleUploader({ bankId }: { bankId: string }) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  async function handleFile(file: File) {
    setError(null);
    setBusy(true);
    try {
      await clientUploadSample(bankId, file);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div
      onDragEnter={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        const file = e.dataTransfer.files?.[0];
        if (file) handleFile(file);
      }}
      className={`rounded-2xl border-2 border-dashed p-8 text-center transition ${
        dragOver
          ? "border-violet bg-violet/5"
          : "border-ink/15 bg-white/30 hover:bg-white/60"
      }`}
    >
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) handleFile(f);
        }}
        disabled={busy}
      />
      <p className="font-display text-2xl tracking-tight">
        {busy ? "Uploading…" : "Drop a sample exam"}
      </p>
      <p className="mt-2 text-sm text-ink/55">
        Supports .pdf, .docx, .doc, .odt, .rtf — single file at a time.
      </p>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        disabled={busy}
        className="mt-6 rounded-full bg-ink px-5 py-2.5 text-sm font-medium text-ivory transition hover:bg-violet disabled:opacity-40"
      >
        Choose file
      </button>
      {error ? <p className="mt-3 text-sm text-red-600">{error}</p> : null}
    </div>
  );
}
