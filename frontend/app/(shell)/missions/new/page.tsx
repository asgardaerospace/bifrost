"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/api";
import type { MissionPriority, MissionStatus } from "@/types/api";

const PRIORITIES: MissionPriority[] = ["low", "normal", "high", "critical"];
const STATUSES: MissionStatus[] = [
  "planning",
  "active",
  "paused",
  "completed",
  "cancelled",
];

export default function NewMissionPage() {
  const router = useRouter();
  const [codename, setCodename] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [missionType, setMissionType] = useState("strategic");
  const [priority, setPriority] = useState<MissionPriority>("normal");
  const [status, setStatus] = useState<MissionStatus>("planning");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const created = await api.createMission({
        codename: codename.trim(),
        name: name.trim(),
        description: description.trim() || null,
        mission_type: missionType,
        priority,
        status,
      });
      router.push(`/missions/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "create failed");
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 p-6">
      <header>
        <div className="font-mono text-2xs uppercase tracking-[0.3em] text-accent/80">
          ▸ new mission
        </div>
        <h1 className="mt-1 text-2xl font-semibold text-inkhi text-accent-glow">
          Define mission
        </h1>
        <p className="mt-1 text-xs text-mute2">
          Codename is short, uppercase, unique. Existing CRM entities can be
          linked from the mission detail view after creation.
        </p>
      </header>

      <form
        onSubmit={onSubmit}
        className="flex flex-col gap-4 rounded-lg border border-border/60 bg-panel/60 p-5 glass"
      >
        <label className="flex flex-col gap-1">
          <span className="font-mono text-2xs uppercase tracking-widest text-mute2">
            codename
          </span>
          <input
            value={codename}
            onChange={(e) => setCodename(e.target.value.toUpperCase())}
            required
            placeholder="STARLINE-1"
            className="rounded-md border border-border bg-bgdeep px-3 py-2 font-mono text-sm text-inkhi outline-none focus:border-accent"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="font-mono text-2xs uppercase tracking-widest text-mute2">
            name
          </span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            placeholder="Starline 1 — propulsion qualification"
            className="rounded-md border border-border bg-bgdeep px-3 py-2 text-sm text-inkhi outline-none focus:border-accent"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="font-mono text-2xs uppercase tracking-widest text-mute2">
            description
          </span>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="rounded-md border border-border bg-bgdeep px-3 py-2 text-sm text-ink outline-none focus:border-accent"
          />
        </label>
        <div className="grid grid-cols-3 gap-3">
          <label className="flex flex-col gap-1">
            <span className="font-mono text-2xs uppercase tracking-widest text-mute2">
              type
            </span>
            <input
              value={missionType}
              onChange={(e) => setMissionType(e.target.value)}
              className="rounded-md border border-border bg-bgdeep px-3 py-2 text-sm text-ink outline-none focus:border-accent"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="font-mono text-2xs uppercase tracking-widest text-mute2">
              priority
            </span>
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value as MissionPriority)}
              className="rounded-md border border-border bg-bgdeep px-3 py-2 text-sm text-ink outline-none focus:border-accent"
            >
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="font-mono text-2xs uppercase tracking-widest text-mute2">
              status
            </span>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as MissionStatus)}
              className="rounded-md border border-border bg-bgdeep px-3 py-2 text-sm text-ink outline-none focus:border-accent"
            >
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
        </div>

        {error && (
          <div className="rounded-md border border-red/40 bg-red/10 px-3 py-2 font-mono text-2xs text-red">
            {error}
          </div>
        )}

        <div className="flex items-center justify-end gap-2 border-t border-border/60 pt-4">
          <button
            type="button"
            onClick={() => router.back()}
            className="rounded-md border border-border px-3 py-2 text-xs text-mute2 hover:border-border2 hover:text-ink"
          >
            cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="chip-accent rounded-md px-4 py-2 text-xs font-semibold uppercase tracking-widest hover:bg-accent/30 disabled:opacity-50"
          >
            {submitting ? "creating…" : "create mission"}
          </button>
        </div>
      </form>
    </div>
  );
}
