"use client";

import { useState, type FormEvent, type KeyboardEvent } from "react";

const EXAMPLES = [
  "Show investor pipeline",
  "Show overdue follow-ups",
  "Rank investors most likely to close",
  "Show pending approvals",
  "What investor actions matter most this week",
];

export function CommandInput({
  onSubmit,
  busy,
}: {
  onSubmit: (text: string) => void;
  busy: boolean;
}) {
  const [text, setText] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const v = text.trim();
    if (!v || busy) return;
    onSubmit(v);
    setText("");
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as unknown as FormEvent);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="rounded-lg border border-border bg-panel focus-within:border-accent">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Enter a command. Examples: show investor pipeline, rank investors most likely to close"
          rows={3}
          disabled={busy}
          className="w-full resize-none bg-transparent px-4 py-3 font-mono text-sm outline-none placeholder:text-muted/60 disabled:opacity-50"
          autoFocus
        />
        <div className="flex items-center justify-between border-t border-border px-3 py-2">
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
            enter to submit · shift+enter for newline
          </span>
          <button
            type="submit"
            disabled={busy || text.trim().length === 0}
            className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-bg disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy ? "Running…" : "Submit"}
          </button>
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            type="button"
            onClick={() => setText(ex)}
            className="rounded border border-border px-2 py-1 font-mono text-[11px] text-muted hover:border-accent hover:text-accent"
          >
            {ex}
          </button>
        ))}
      </div>
    </form>
  );
}
