"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { LocaleToggle } from "@/components/LocaleToggle";
import { useI18n } from "@/components/I18nProvider";
import { clientLogin } from "@/lib/client";

export default function LoginPage() {
  const router = useRouter();
  const { messages: m } = useI18n();
  const [username, setUsername] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await clientLogin(username.trim());
      router.replace("/");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative mx-auto flex min-h-screen max-w-md items-center px-6">
      <div className="absolute right-6 top-6">
        <LocaleToggle />
      </div>

      <div className="w-full">
        <p className="text-xs uppercase tracking-[0.18em] text-ink/50">
          {m.login.eyebrow}
        </p>
        <h1 className="mt-4 font-display text-5xl tracking-tight">
          {m.login.welcome}
        </h1>
        <p className="mt-3 text-ink/60">{m.login.subtitle}</p>

        <form onSubmit={onSubmit} className="mt-10 space-y-4">
          <label className="block">
            <span className="text-xs uppercase tracking-wider text-ink/60">
              {m.login.usernameLabel}
            </span>
            <input
              autoFocus
              name="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder={m.login.usernamePlaceholder}
              className="mt-2 w-full rounded-xl border border-ink/15 bg-white/70 px-4 py-3 text-lg outline-none ring-violet/0 transition focus:border-violet focus:ring-2 focus:ring-violet/30"
              disabled={busy}
              minLength={1}
              maxLength={32}
              required
            />
          </label>

          {error ? <p className="text-sm text-red-600">{error}</p> : null}

          <button
            type="submit"
            disabled={busy || username.trim().length === 0}
            className="w-full rounded-full bg-ink px-6 py-3 text-sm font-medium text-ivory shadow-soft transition hover:bg-violet disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy ? m.login.signingIn : m.login.signIn}
          </button>

          <p className="text-xs text-ink/40">{m.login.note}</p>
        </form>
      </div>
    </div>
  );
}
