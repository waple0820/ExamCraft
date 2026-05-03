import Link from "next/link";
import { redirect } from "next/navigation";

import { SignOutButton } from "@/components/SignOutButton";
import { getMe } from "@/lib/server";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const me = await getMe();
  if (!me) redirect("/login");

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-ink/5 bg-ivory/85 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <Link href="/" className="flex items-baseline gap-3">
            <span className="font-display text-xl tracking-tight">ExamCraft</span>
            <span className="text-xs uppercase tracking-[0.18em] text-ink/40">
              workshop
            </span>
          </Link>
          <div className="flex items-center gap-4">
            <span className="text-sm text-ink/60">{me.username}</span>
            <SignOutButton />
          </div>
        </div>
      </header>
      <div className="mx-auto max-w-5xl px-6 py-12">{children}</div>
    </div>
  );
}
