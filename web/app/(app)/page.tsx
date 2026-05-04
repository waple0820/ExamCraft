import Link from "next/link";

import { CreateBankCard } from "@/components/CreateBankCard";
import { formatDate } from "@/lib/format";
import { getMessages } from "@/lib/i18n/server";
import { listBanks } from "@/lib/server";

export const dynamic = "force-dynamic";

export default async function Dashboard() {
  const [banks, { messages: m, locale }] = await Promise.all([
    listBanks(),
    getMessages(),
  ]);

  const STATUS_COPY: Record<string, { label: string; tone: string }> = {
    idle: { label: m.dashboard.statusIdle, tone: "text-ink/40" },
    running: { label: m.dashboard.statusRunning, tone: "text-violet" },
    done: { label: m.dashboard.statusReady, tone: "text-teal" },
    error: { label: m.dashboard.statusError, tone: "text-red-600" },
  };


  return (
    <div className="space-y-12">
      <div className="flex items-end justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-ink/50">
            {m.dashboard.eyebrow}
          </p>
          <h1 className="mt-3 font-display text-4xl tracking-tight">
            {m.dashboard.title}
          </h1>
        </div>
        <p className="max-w-xs text-right text-sm text-ink/55">
          {m.dashboard.intro}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        {banks.map((b) => {
          const status = STATUS_COPY[b.analysis_status] ?? STATUS_COPY.idle;
          return (
            <Link
              key={b.id}
              href={{ pathname: `/banks/${b.id}` }}
              className="group rounded-2xl border border-ink/10 bg-white/70 p-6 shadow-soft transition hover:border-violet/40 hover:shadow-lg"
            >
              <div className="flex items-baseline justify-between">
                <h2 className="font-display text-2xl tracking-tight group-hover:text-violet">
                  {b.name}
                </h2>
                <span
                  className={`text-xs uppercase tracking-wider ${status.tone}`}
                >
                  {status.label}
                </span>
              </div>
              {b.description ? (
                <p className="mt-3 line-clamp-2 text-sm text-ink/60">
                  {b.description}
                </p>
              ) : (
                <p className="mt-3 text-sm italic text-ink/30">
                  {m.dashboard.noDescription}
                </p>
              )}
              <p className="mt-6 text-xs uppercase tracking-wider text-ink/35">
                {m.dashboard.createdAt(formatDate(b.created_at, locale))}
              </p>
            </Link>
          );
        })}

        <CreateBankCard />
      </div>

      {banks.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-ink/15 p-10 text-center text-sm text-ink/50">
          {m.dashboard.empty}
        </div>
      ) : null}
    </div>
  );
}
