import Link from "next/link";
import { redirect } from "next/navigation";

import { LocaleToggle } from "@/components/LocaleToggle";
import { SignOutButton } from "@/components/SignOutButton";
import { getMessages } from "@/lib/i18n/server";
import { getMe } from "@/lib/server";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const me = await getMe();
  if (!me) redirect("/login");
  const { messages: m } = await getMessages();

  return (
    <div className="min-h-screen">
      <header
        data-no-print
        className="sticky top-0 z-10 border-b border-ink/5 bg-ivory/85 backdrop-blur"
      >
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <Link href="/" className="flex items-baseline">
            <span className="font-display text-xl tracking-tight">
              {m.brand.name}
            </span>
          </Link>
          <div className="flex items-center gap-4">
            <span className="text-sm text-ink/60">{me.username}</span>
            <LocaleToggle />
            <SignOutButton />
          </div>
        </div>
      </header>
      <div className="mx-auto max-w-5xl px-6 py-12">{children}</div>
    </div>
  );
}
