"use client";

import Image from "next/image";

import { backendUrl, type GeneratedPage } from "@/lib/api";

export function PageGallery({ pages }: { pages: GeneratedPage[] }) {
  if (pages.length === 0) {
    return (
      <section>
        <h2 className="text-xs uppercase tracking-[0.16em] text-ink/45">Pages</h2>
        <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
          {[1, 2, 3, 4].map((n) => (
            <div
              key={n}
              className="aspect-[3/4] animate-pulse rounded-xl bg-ink/5"
            />
          ))}
        </div>
      </section>
    );
  }

  return (
    <section>
      <h2 className="text-xs uppercase tracking-[0.16em] text-ink/45">
        Pages — {pages.filter((p) => p.image_url).length}/{pages.length} ready
      </h2>
      <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
        {pages.map((p) => (
          <figure
            key={p.page_number}
            className="overflow-hidden rounded-xl border border-ink/10 bg-white/60 shadow-soft"
          >
            <div className="relative aspect-[3/4] bg-ink/5">
              {p.image_url ? (
                <Image
                  src={backendUrl(p.image_url)}
                  alt={`Page ${p.page_number}`}
                  fill
                  className="object-contain"
                  unoptimized
                />
              ) : p.status === "error" ? (
                <div className="flex h-full flex-col items-center justify-center gap-1 px-4 text-center">
                  <span className="text-xs uppercase tracking-wider text-red-600">
                    failed
                  </span>
                  <span className="text-xs text-ink/45">
                    chat to retry this page
                  </span>
                </div>
              ) : (
                <div className="flex h-full items-center justify-center text-xs text-ink/40">
                  rendering…
                </div>
              )}
            </div>
            <figcaption className="flex items-center justify-between px-3 py-2 text-xs text-ink/55">
              <span>Page {p.page_number}</span>
              <span
                className={
                  p.status === "done"
                    ? "text-teal"
                    : p.status === "error"
                      ? "text-red-600"
                      : ""
                }
              >
                {p.status}
              </span>
            </figcaption>
          </figure>
        ))}
      </div>
    </section>
  );
}
