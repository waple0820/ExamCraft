import Link from "next/link";

import type { GenerationSummary } from "@/lib/api";

const STATUS_COPY: Record<string, { label: string; tone: string }> = {
  queued: { label: "queued", tone: "text-ink/45" },
  running: { label: "in progress", tone: "text-violet" },
  done: { label: "ready", tone: "text-teal" },
  failed: { label: "failed", tone: "text-red-600" },
};

export function GenerationsList({ items }: { items: GenerationSummary[] }) {
  if (items.length === 0) {
    return (
      <p className="mt-2 text-sm italic text-ink/40">
        No generations yet.
      </p>
    );
  }
  return (
    <ul className="mt-4 divide-y divide-ink/5">
      {items.map((g) => {
        const status = STATUS_COPY[g.status] ?? STATUS_COPY.queued;
        return (
          <li key={g.id}>
            <Link
              href={`/generations/${g.id}` as never}
              className="flex items-center justify-between gap-4 py-4 transition hover:text-violet"
            >
              <div>
                <p className="text-sm font-medium">
                  Generation · {new Date(g.created_at).toLocaleString()}
                </p>
                <p className="mt-1 text-xs text-ink/45">
                  <span className={status.tone}>{status.label}</span>
                  {" · "}
                  {g.page_count} page{g.page_count === 1 ? "" : "s"}
                  {g.status === "running" ? (
                    <> · {Math.round(g.progress_pct * 100)}%</>
                  ) : null}
                </p>
              </div>
              <span aria-hidden className="text-ink/30">
                →
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
