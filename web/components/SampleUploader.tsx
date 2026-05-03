"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Check, FileText, Loader2, UploadCloud, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { useI18n } from "@/components/I18nProvider";
import { clientUploadSample } from "@/lib/client";

const ACCEPT = ".pdf,.docx,.doc,.odt,.rtf";
const ACCEPTED_EXT = /\.(pdf|docx|doc|odt|rtf)$/i;

type UploadJob = {
  localId: string;
  fileName: string;
  fileSize: number;
  phase: "uploading" | "success" | "error";
  error?: string;
};

export function SampleUploader({ bankId }: { bankId: string }) {
  const router = useRouter();
  const { messages: m } = useI18n();
  const inputRef = useRef<HTMLInputElement>(null);
  const [jobs, setJobs] = useState<UploadJob[]>([]);
  const [dragOver, setDragOver] = useState(false);

  function startTimerFor(localId: string, ms: number) {
    setTimeout(() => {
      setJobs((prev) => prev.filter((j) => j.localId !== localId));
    }, ms);
  }

  async function handleFiles(fileList: FileList | null | undefined) {
    if (!fileList || fileList.length === 0) return;
    const files = Array.from(fileList).filter((f) => ACCEPTED_EXT.test(f.name));
    if (files.length === 0) return;

    for (const file of files) {
      const localId = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      setJobs((prev) => [
        ...prev,
        {
          localId,
          fileName: file.name,
          fileSize: file.size,
          phase: "uploading",
        },
      ]);
      try {
        await clientUploadSample(bankId, file);
        setJobs((prev) =>
          prev.map((j) =>
            j.localId === localId ? { ...j, phase: "success" } : j,
          ),
        );
        router.refresh();
        startTimerFor(localId, 5000);
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        setJobs((prev) =>
          prev.map((j) =>
            j.localId === localId
              ? { ...j, phase: "error", error: message }
              : j,
          ),
        );
      }
    }
    if (inputRef.current) inputRef.current.value = "";
  }

  function dismiss(localId: string) {
    setJobs((prev) => prev.filter((j) => j.localId !== localId));
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
        handleFiles(e.dataTransfer.files);
      }}
      className={`rounded-2xl border-2 border-dashed p-6 transition ${
        dragOver
          ? "border-violet bg-violet/5"
          : "border-ink/15 bg-white/30"
      }`}
    >
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        multiple
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />

      <AnimatePresence initial={false}>
        {jobs.length > 0 ? (
          <motion.ul
            key="jobs"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="mb-5 space-y-2"
          >
            <AnimatePresence initial={false}>
              {jobs.map((j) => (
                <motion.li
                  key={j.localId}
                  layout
                  initial={{ opacity: 0, y: -10, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.96, transition: { duration: 0.2 } }}
                  transition={{ duration: 0.25, ease: "easeOut" }}
                >
                  <UploadChip
                    job={j}
                    uploading={m.uploader.uploadingFile(j.fileName)}
                    uploadingHint={m.uploader.uploadingHint}
                    successTitle={m.uploader.successTitle(j.fileName)}
                    successHint={m.uploader.successHint}
                    onDismiss={() => dismiss(j.localId)}
                  />
                </motion.li>
              ))}
            </AnimatePresence>
          </motion.ul>
        ) : null}
      </AnimatePresence>

      <div className="flex flex-col items-center gap-3 text-center">
        <UploadCloud
          className={`size-9 ${dragOver ? "text-violet" : "text-ink/30"}`}
          strokeWidth={1.5}
        />
        <p className="font-display text-2xl tracking-tight text-ink">
          {m.uploader.dropPrompt}
        </p>
        <p className="text-sm text-ink/55">{m.uploader.supportsHint}</p>
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="mt-1 rounded-full bg-ink px-5 py-2.5 text-sm font-medium text-ivory transition hover:bg-violet"
        >
          {m.uploader.chooseFile}
        </button>
      </div>
    </div>
  );
}

function UploadChip({
  job,
  uploading,
  uploadingHint,
  successTitle,
  successHint,
  onDismiss,
}: {
  job: UploadJob;
  uploading: string;
  uploadingHint: string;
  successTitle: string;
  successHint: string;
  onDismiss: () => void;
}) {
  const accent =
    job.phase === "success"
      ? "border-teal/30 bg-teal/5"
      : job.phase === "error"
        ? "border-red-300 bg-red-50"
        : "border-ink/10 bg-white";

  return (
    <div
      className={`flex items-center gap-3 rounded-xl border px-4 py-3 text-left ${accent}`}
    >
      <div
        className={`flex size-10 shrink-0 items-center justify-center rounded-lg ${
          job.phase === "success"
            ? "bg-teal/15 text-teal"
            : job.phase === "error"
              ? "bg-red-100 text-red-600"
              : "bg-ink/5 text-ink/55"
        }`}
      >
        {job.phase === "success" ? (
          <Check className="size-5" />
        ) : job.phase === "error" ? (
          <X className="size-5" />
        ) : (
          <FileText className="size-5" />
        )}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-ink">
          {job.phase === "success" ? successTitle : job.fileName}
        </p>
        <p className="mt-0.5 truncate text-xs text-ink/55">
          {job.phase === "uploading" ? (
            <>
              {formatBytes(job.fileSize)} · {uploadingHint}
            </>
          ) : job.phase === "success" ? (
            successHint
          ) : (
            <span className="text-red-600">{job.error}</span>
          )}
        </p>
      </div>
      {job.phase === "uploading" ? (
        <Loader2 className="size-4 shrink-0 animate-spin text-violet" />
      ) : (
        <button
          type="button"
          onClick={onDismiss}
          className="shrink-0 text-ink/30 transition hover:text-ink/70"
          aria-label="dismiss"
        >
          <X className="size-4" />
        </button>
      )}
    </div>
  );
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
