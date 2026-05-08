"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";

import { bindRealtimeToQueryClient } from "@/lib/realtime-store";
import { getWsClient } from "@/lib/ws-client";

type ShellState = {
  selectedMissionId: number | null;
  setSelectedMissionId: (id: number | null) => void;
  focusedQueueItemId: number | null;
  setFocusedQueueItemId: (id: number | null) => void;
};

const Ctx = createContext<ShellState | null>(null);

export function ShellProvider({ children }: { children: ReactNode }) {
  const [selectedMissionId, setSelectedMissionIdRaw] = useState<number | null>(null);
  const [focusedQueueItemId, setFocusedQueueItemId] = useState<number | null>(null);
  const qc = useQueryClient();

  // Bind the realtime ws client to this QueryClient on first mount (per page).
  // Existing CRM routes don't render this provider, so they remain WS-free.
  useEffect(() => {
    const teardown = bindRealtimeToQueryClient(qc);
    return () => teardown();
  }, [qc]);

  // Keep the ws client's mission focus in sync with the shell selection so
  // the backend records who is viewing which mission.
  function setSelectedMissionId(id: number | null) {
    setSelectedMissionIdRaw(id);
    try {
      getWsClient().setMissionFocus(id);
    } catch {
      // pre-connect; the client will resend focus on connect.
    }
  }

  return (
    <Ctx.Provider
      value={{
        selectedMissionId,
        setSelectedMissionId,
        focusedQueueItemId,
        setFocusedQueueItemId,
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useShell(): ShellState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useShell must be used inside <ShellProvider>");
  return v;
}
