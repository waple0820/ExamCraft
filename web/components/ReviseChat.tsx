"use client";

import { useEffect, useRef, useState } from "react";

import type { ChatMessage } from "@/lib/api";
import { clientPostChat } from "@/lib/client";

export function ReviseChat({
  jobId,
  initialMessages,
  jobStatus,
  onAssistantReply,
}: {
  jobId: string;
  initialMessages: ChatMessage[];
  jobStatus: "queued" | "running" | "done" | "failed";
  onAssistantReply?: (content: string) => void;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMessages(initialMessages);
  }, [initialMessages]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  const inputDisabled = busy || jobStatus === "running" || jobStatus === "queued";

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const text = content.trim();
    if (!text) return;
    setError(null);
    setBusy(true);
    try {
      const reply = await clientPostChat(jobId, text);
      setMessages((m) => [
        ...m,
        {
          id: reply.id,
          role: "user",
          content: text,
          created_at: reply.created_at,
        },
      ]);
      setContent("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  // Echo through the SSE-driven listener: GenerationWatch will call
  // onAssistantReply when an assistant turn arrives. We append it below.
  useEffect(() => {
    if (!onAssistantReply) return;
    // expose a way for parent to push assistant turns
    (window as unknown as { __examcraftPushAssistant?: (s: string) => void }).__examcraftPushAssistant = (s: string) => {
      setMessages((m) => [
        ...m,
        {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: s,
          created_at: new Date().toISOString(),
        },
      ]);
    };
    return () => {
      (window as unknown as { __examcraftPushAssistant?: (s: string) => void }).__examcraftPushAssistant = undefined;
    };
  }, [onAssistantReply]);

  return (
    <aside className="rounded-2xl border border-ink/10 bg-white/60 p-6 shadow-soft">
      <div className="flex items-baseline justify-between">
        <h2 className="font-display text-2xl tracking-tight">Talk it over</h2>
        <span className="text-xs uppercase tracking-wider text-ink/40">
          edits the spec
        </span>
      </div>
      <p className="mt-2 text-sm text-ink/55">
        Spot something off? Tell ExamCraft. It revises the spec and re-renders
        only the pages that changed.
      </p>

      <div
        ref={scrollRef}
        className="mt-4 max-h-[420px] space-y-3 overflow-y-auto rounded-xl border border-ink/5 bg-ivory/50 p-4"
      >
        {messages.length === 0 ? (
          <p className="text-sm italic text-ink/40">
            No revisions yet. Examples: &ldquo;把第3题换成关于二次函数的题&rdquo;,
            &ldquo;再加一道圆的解答题&rdquo;, &ldquo;难度调低一点&rdquo;.
          </p>
        ) : (
          messages.map((m) => (
            <div
              key={m.id}
              className={
                m.role === "user"
                  ? "ml-auto max-w-[80%] rounded-2xl bg-violet/10 px-3 py-2 text-sm text-ink/85"
                  : "max-w-[80%] rounded-2xl bg-white px-3 py-2 text-sm text-ink/80 shadow-soft"
              }
            >
              {m.content}
            </div>
          ))
        )}
      </div>

      <form onSubmit={onSubmit} className="mt-4 space-y-2">
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          rows={3}
          maxLength={2000}
          placeholder={
            jobStatus === "running"
              ? "Working on a previous revision…"
              : "What should change?"
          }
          disabled={inputDisabled}
          className="w-full resize-none rounded-xl border border-ink/15 bg-white px-3 py-2 text-sm outline-none focus:border-violet focus:ring-2 focus:ring-violet/30 disabled:opacity-60"
        />
        {error ? <p className="text-sm text-red-600">{error}</p> : null}
        <div className="flex items-center justify-between">
          <span className="text-xs text-ink/35">
            {jobStatus === "done"
              ? "Ready"
              : jobStatus === "running"
                ? "Wait for current run"
                : jobStatus === "failed"
                  ? "Generation failed — fix on the bank page"
                  : "Queued"}
          </span>
          <button
            type="submit"
            disabled={inputDisabled || !content.trim()}
            className="rounded-full bg-ink px-4 py-2 text-sm font-medium text-ivory hover:bg-violet disabled:opacity-40"
          >
            {busy ? "Sending…" : "Send"}
          </button>
        </div>
      </form>
    </aside>
  );
}
