"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { useI18n } from "@/components/I18nProvider";
import { clientLogout } from "@/lib/client";

export function SignOutButton() {
  const router = useRouter();
  const { messages: m } = useI18n();
  const [busy, setBusy] = useState(false);

  async function onClick() {
    setBusy(true);
    try {
      await clientLogout();
    } finally {
      setBusy(false);
      router.replace("/login");
      router.refresh();
    }
  }

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={busy}
      className="text-xs uppercase tracking-[0.14em] text-ink/45 transition hover:text-violet disabled:opacity-40"
    >
      {busy ? "…" : m.brand.signOut}
    </button>
  );
}
