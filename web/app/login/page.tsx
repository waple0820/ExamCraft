"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { clientLogin } from "@/lib/client";

export default function LoginPage() {
  const router = useRouter();
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
    <div className="mx-auto flex min-h-screen max-w-md items-center px-6">
      <div className="w-full">
        <p className="text-xs uppercase tracking-[0.18em] text-ink/50">ExamCraft</p>
        <h1 className="mt-4 font-display text-5xl tracking-tight">Welcome.</h1>
        <p className="mt-3 text-ink/60">
          Pick a username — we&apos;ll remember it.
        </p>

        <form onSubmit={onSubmit} className="mt-10 space-y-4">
          <label className="block">
            <span className="text-xs uppercase tracking-wider text-ink/60">
              Username
            </span>
            <input
              autoFocus
              name="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="爸爸 / mom / alice"
              className="mt-2 w-full rounded-xl border border-ink/15 bg-white/70 px-4 py-3 text-lg outline-none ring-violet/0 transition focus:border-violet focus:ring-2 focus:ring-violet/30"
              disabled={busy}
              minLength={1}
              maxLength={32}
              required
            />
          </label>

          {error ? (
            <p className="text-sm text-red-600">{error}</p>
          ) : null}

          <button
            type="submit"
            disabled={busy || username.trim().length === 0}
            className="w-full rounded-full bg-ink px-6 py-3 text-sm font-medium text-ivory shadow-soft transition hover:bg-violet disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy ? "Signing in…" : "Sign in"}
          </button>

          <p className="text-xs text-ink/40">
            No password — this is a personal local app. Switch users any time
            by signing in with a different name.
          </p>
        </form>
      </div>
    </div>
  );
}
