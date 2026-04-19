"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { ActionItem, CommandResponse } from "@/types/api";
import { api } from "@/lib/api";

export interface SelectedEntity {
  kind: "action" | "entity";
  id: string;
  ref?: string;
  label?: string;
  action?: ActionItem;
  entityType?: string;
  entityId?: number;
}

interface WorkspaceState {
  selected: SelectedEntity | null;
  setSelected: (s: SelectedEntity | null) => void;

  paletteOpen: boolean;
  setPaletteOpen: (v: boolean) => void;

  lastResponse: CommandResponse | null;
  runCommand: (text: string) => Promise<CommandResponse | null>;
  running: boolean;

  toast: { msg: string; tone: "info" | "ok" | "err" } | null;
  flash: (msg: string, tone?: "info" | "ok" | "err") => void;
}

const Ctx = createContext<WorkspaceState | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [selected, setSelected] = useState<SelectedEntity | null>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [lastResponse, setLastResponse] = useState<CommandResponse | null>(
    null,
  );
  const [running, setRunning] = useState(false);
  const [toast, setToast] = useState<WorkspaceState["toast"]>(null);
  const toastRef = useRef<number | null>(null);

  const flash = useCallback<WorkspaceState["flash"]>((msg, tone = "info") => {
    setToast({ msg, tone });
    if (toastRef.current) window.clearTimeout(toastRef.current);
    toastRef.current = window.setTimeout(() => setToast(null), 2400);
  }, []);

  const runCommand = useCallback<WorkspaceState["runCommand"]>(
    async (text) => {
      const trimmed = text.trim();
      if (!trimmed) return null;
      setRunning(true);
      try {
        const res = await api.submitCommand({ text: trimmed, actor: "ui" });
        setLastResponse(res);
        flash(
          res.status === "completed"
            ? `✓ ${res.classification.command_class}: ${res.output.headline}`
            : `${res.status}: ${res.output.headline}`,
          res.status === "completed" ? "ok" : "info",
        );
        return res;
      } catch (e) {
        flash((e as Error).message, "err");
        return null;
      } finally {
        setRunning(false);
      }
    },
    [flash],
  );

  // Global keybindings
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const typing =
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable);
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((v) => !v);
        return;
      }
      if (e.key === "/" && !typing) {
        e.preventDefault();
        setPaletteOpen(true);
        return;
      }
      if (e.key === "Escape") {
        if (paletteOpen) setPaletteOpen(false);
        else if (selected) setSelected(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [paletteOpen, selected]);

  const value = useMemo(
    () => ({
      selected,
      setSelected,
      paletteOpen,
      setPaletteOpen,
      lastResponse,
      runCommand,
      running,
      toast,
      flash,
    }),
    [selected, paletteOpen, lastResponse, runCommand, running, toast, flash],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useWorkspace() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useWorkspace outside WorkspaceProvider");
  return v;
}
