"use client";

import { useEffect, useRef, useState } from "react";
import { useWorkspace } from "./workspace-context";
import type { CommandResponse, CommandOutput } from "@/types/api";

const SUGGESTIONS = [
  "brief me",
  "executive briefing",
  "show action queue",
  "show alerts",
  "rank my pipeline",
  "show overdue follow-ups",
  "review approvals",
  "list active programs",
  "list high value programs",
  "list overdue programs",
  "list active campaigns",
  "list market follow-ups",
  "list qualified suppliers",
  "list engine writes",
  "draft follow-up for opportunity 1",
  "brief on opportunity 1",
];

export function CommandBar() {
  const { paletteOpen, setPaletteOpen, runCommand, running, lastResponse } =
    useWorkspace();
  const [text, setText] = useState("");
  const [cursor, setCursor] = useState(0);
  const [preview, setPreview] = useState<CommandResponse | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (paletteOpen) {
      setTimeout(() => inputRef.current?.focus(), 0);
    } else {
      setText("");
      setCursor(0);
      setPreview(null);
    }
  }, [paletteOpen]);

  if (!paletteOpen) return null;

  const matches = text
    ? SUGGESTIONS.filter((s) =>
        s.toLowerCase().includes(text.toLowerCase()),
      ).slice(0, 8)
    : SUGGESTIONS.slice(0, 8);

  const parsed = parseIntent(text);

  const submit = async (override?: string) => {
    const t = override ?? text;
    const res = await runCommand(t);
    if (res) setPreview(res);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 pt-[12vh]"
      onClick={() => setPaletteOpen(false)}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-[720px] max-w-[92vw] border border-border2 bg-panel shadow-2xl"
      >
        <div className="flex items-center gap-2 border-b border-border px-3 py-2">
          <span className="font-mono text-2xs uppercase tracking-wider text-muted">
            cmd
          </span>
          <input
            ref={inputRef}
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setCursor(0);
            }}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setCursor((c) => Math.min(c + 1, matches.length - 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setCursor((c) => Math.max(c - 1, 0));
              } else if (e.key === "Tab") {
                e.preventDefault();
                if (matches[cursor]) setText(matches[cursor]);
              } else if (e.key === "Enter") {
                e.preventDefault();
                if (!text && matches[cursor]) submit(matches[cursor]);
                else submit();
              }
            }}
            placeholder="type a command — e.g. 'brief me', 'rank pipeline', 'draft follow-up for opportunity 3'"
            className="flex-1 bg-transparent text-md text-inkhi outline-none placeholder:text-muted"
          />
          <span className="kbd">esc</span>
        </div>

        <div className="flex items-center gap-2 border-b border-border px-3 py-1 text-2xs font-mono uppercase tracking-wider text-muted">
          <span>parse:</span>
          <span className="text-mute2">
            {parsed.class}
            {parsed.entity ? ` · ${parsed.entity}` : ""}
          </span>
          {running && <span className="ml-auto text-blue">running…</span>}
        </div>

        {!preview && (
          <ul className="max-h-[40vh] overflow-y-auto py-1">
            {matches.map((s, i) => (
              <li key={s}>
                <button
                  onMouseEnter={() => setCursor(i)}
                  onClick={() => submit(s)}
                  className={`flex w-full items-center justify-between px-3 py-1.5 text-left text-sm ${
                    i === cursor
                      ? "bg-panel2 text-inkhi"
                      : "text-mute2 hover:bg-panel2 hover:text-ink"
                  }`}
                >
                  <span className="font-mono">{s}</span>
                  {i === cursor && (
                    <span className="kbd">enter</span>
                  )}
                </button>
              </li>
            ))}
            {matches.length === 0 && (
              <li className="px-3 py-3 text-sm text-muted">
                No suggestions — press Enter to run raw text.
              </li>
            )}
          </ul>
        )}

        {preview && <PreviewPanel response={preview} />}

        <div className="flex items-center justify-between border-t border-border px-3 py-1.5 text-2xs font-mono uppercase tracking-wider text-muted">
          <div className="flex items-center gap-3">
            <span>
              <span className="kbd">↑↓</span> nav
            </span>
            <span>
              <span className="kbd">tab</span> complete
            </span>
            <span>
              <span className="kbd">enter</span> run
            </span>
          </div>
          {lastResponse && (
            <span className="text-mute2">
              last: {lastResponse.classification.command_class} ·{" "}
              {lastResponse.duration_ms}ms
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function parseIntent(text: string): { class: string; entity?: string } {
  const t = text.toLowerCase();
  if (!t) return { class: "—" };
  if (/\bbrief\b|briefing\b/.test(t)) return matchEntity(t, "brief");
  if (/\brank\b|prioriti/.test(t)) return matchEntity(t, "analyze");
  if (/\bdraft\b/.test(t)) return matchEntity(t, "draft");
  if (/\breview\b|approval/.test(t)) return { class: "review" };
  if (/\blist\b|\bshow\b/.test(t)) return matchEntity(t, "read");
  if (/overdue|stale|due/.test(t)) return { class: "analyze" };
  if (/action queue|alerts/.test(t)) return { class: "read" };
  return { class: "read" };
}

function matchEntity(t: string, cls: string): { class: string; entity?: string } {
  const m = t.match(
    /(opportunity|program|supplier|account|campaign|investor|firm)\s+(\d+|#\d+|[\w-]+)/,
  );
  if (m) return { class: cls, entity: `${m[1]} ${m[2]}` };
  return { class: cls };
}

function PreviewPanel({ response }: { response: CommandResponse }) {
  const { setPaletteOpen } = useWorkspace();
  const out = response.output;
  return (
    <div className="max-h-[50vh] overflow-y-auto border-t border-border p-3 text-sm">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-2xs font-mono uppercase tracking-wider text-muted">
            {response.classification.command_class} ·{" "}
            {response.classification.confidence} · {response.duration_ms}ms
          </div>
          <div className="mt-0.5 text-md font-semibold text-inkhi">
            {out.headline}
          </div>
        </div>
        <button
          onClick={() => setPaletteOpen(false)}
          className="border border-border2 px-2 py-1 font-mono text-2xs uppercase tracking-wider text-ink hover:border-blue hover:text-blue"
        >
          dismiss
        </button>
      </div>

      <div className="mt-3">
        <OutputView output={out} />
      </div>
    </div>
  );
}

function OutputView({ output }: { output: CommandOutput }) {
  switch (output.output_type) {
    case "summary":
      return (
        <div className="flex flex-col gap-2 text-sm">
          {output.key_insights.slice(0, 5).map((k, i) => (
            <div key={i} className="text-mute2">
              · {k}
            </div>
          ))}
          {output.next_actions.length > 0 && (
            <div className="mt-2 border-t border-border pt-2">
              <div className="text-2xs font-mono uppercase tracking-wider text-muted">
                next actions
              </div>
              {output.next_actions.map((n, i) => (
                <div key={i} className="text-ink">
                  → {n}
                </div>
              ))}
            </div>
          )}
        </div>
      );
    case "ranked":
      return (
        <div className="flex flex-col">
          {output.items.slice(0, 8).map((it, i) => (
            <div
              key={i}
              className="flex items-center justify-between border-b border-border py-1 text-sm"
            >
              <div>
                <span className="font-mono text-muted">
                  {String(i + 1).padStart(2, "0")}
                </span>{" "}
                <span className="text-ink">
                  {it.opportunity.firm_name ?? `Opp #${it.opportunity.id}`}
                </span>
              </div>
              <span className="font-mono text-2xs text-mute2">
                {Math.round(it.priority_score)}
              </span>
            </div>
          ))}
        </div>
      );
    case "draft":
      return (
        <div className="flex flex-col gap-2">
          <div className="text-2xs font-mono uppercase tracking-wider text-muted">
            draft · {output.communication.channel}
          </div>
          <div className="font-semibold text-inkhi">
            {output.communication.subject ?? "(no subject)"}
          </div>
          <div className="whitespace-pre-wrap border border-border bg-bg p-2 text-xs text-mute2">
            {output.communication.body?.slice(0, 600) ?? "(no body)"}
          </div>
        </div>
      );
    case "executive_briefing":
      return (
        <div className="flex flex-col gap-1">
          {output.briefing.narrative.map((n, i) => (
            <div key={i} className="text-mute2">
              {n}
            </div>
          ))}
        </div>
      );
    case "executive_action_queue":
      return (
        <div className="flex flex-col">
          {output.queue.items.slice(0, 8).map((a) => (
            <div
              key={a.id}
              className="flex items-center justify-between border-b border-border py-1"
            >
              <span className="truncate text-ink">{a.title}</span>
              <span className="font-mono text-2xs text-mute2">
                {a.domain} · P{Math.round(a.priority_score)}
              </span>
            </div>
          ))}
        </div>
      );
    case "executive_alerts":
      return (
        <div className="flex flex-col">
          {output.alerts.alerts.slice(0, 8).map((a) => (
            <div
              key={a.id}
              className="flex items-center justify-between border-b border-border py-1"
            >
              <span className="truncate text-ink">{a.title}</span>
              <span className="font-mono text-2xs text-mute2">
                {a.severity}
              </span>
            </div>
          ))}
        </div>
      );
    case "clarification":
      return (
        <div className="text-sm text-amber">
          {output.message}
          {output.suggested_inputs.length > 0 && (
            <ul className="mt-2 list-disc pl-5 text-mute2">
              {output.suggested_inputs.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          )}
        </div>
      );
    case "unsupported":
      return <div className="text-sm text-red">{output.reason}</div>;
    default:
      return (
        <div className="text-xs text-mute2">
          <pre className="max-h-40 overflow-auto whitespace-pre-wrap font-mono">
            {JSON.stringify(output, null, 2).slice(0, 2000)}
          </pre>
        </div>
      );
  }
}
