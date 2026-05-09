"use client";

/**
 * Realtime state store (Zustand). Sprint 2.
 *
 * Owns:
 *  - websocket connection status
 *  - rolling buffer of recent events (capped, newest first)
 *  - presence map keyed by mission_id
 *  - cursor for /events/replay
 *
 * Side-effects: when a frame arrives, the store invalidates the relevant
 * React Query cache keys so list/detail views re-fetch fresh data without
 * the user reloading. Also maintains the rolling event ribbon for the
 * execution rail.
 */

import { create } from "zustand";
import { useShallow } from "zustand/react/shallow";

import { api } from "./api";
import { getWsClient, type WSStatus } from "./ws-client";
import type { OperationalEventRead, WSFrame } from "@/types/api";

const RECENT_EVENT_BUFFER = 50;

interface RealtimeState {
  status: WSStatus;
  clientId: string | null;
  recentEvents: OperationalEventRead[];
  lastEventId: number;
  presenceByMission: Record<number, number>; // mission_id → operator count
  globalPresenceCount: number;

  // Sprint 8 — operational resilience surface.
  lastSyncAt: number | null;          // ms epoch of last frame received
  reconnectCount: number;             // cumulative reconnects this session
  degradedSince: number | null;       // when status first dropped from open
  hasEverConnected: boolean;          // true after first open

  // actions
  pushEvent: (e: OperationalEventRead) => void;
  setStatus: (s: WSStatus) => void;
  setClientId: (id: string) => void;
  setMissionPresence: (missionId: number, count: number) => void;
  setGlobalPresence: (count: number) => void;
  noteFrame: () => void;
}

export const useRealtimeStore = create<RealtimeState>((set, get) => ({
  status: "idle",
  clientId: null,
  recentEvents: [],
  lastEventId: 0,
  presenceByMission: {},
  globalPresenceCount: 0,
  lastSyncAt: null,
  reconnectCount: 0,
  degradedSince: null,
  hasEverConnected: false,

  pushEvent: (e) =>
    set((s) => ({
      recentEvents: [e, ...s.recentEvents].slice(0, RECENT_EVENT_BUFFER),
      lastEventId: e.id > s.lastEventId ? e.id : s.lastEventId,
      lastSyncAt: Date.now(),
    })),
  setStatus: (status) => {
    const prev = get();
    const becameOpen = status === "open" && prev.status !== "open";
    const lostOpen = prev.status === "open" && status !== "open";
    set({
      status,
      hasEverConnected: prev.hasEverConnected || status === "open",
      reconnectCount: becameOpen && prev.hasEverConnected ? prev.reconnectCount + 1 : prev.reconnectCount,
      degradedSince: lostOpen ? Date.now() : status === "open" ? null : prev.degradedSince,
      lastSyncAt: status === "open" ? Date.now() : prev.lastSyncAt,
    });
  },
  setClientId: (clientId) => set({ clientId }),
  setMissionPresence: (missionId, count) =>
    set((s) => ({
      presenceByMission: { ...s.presenceByMission, [missionId]: count },
    })),
  setGlobalPresence: (count) => set({ globalPresenceCount: count }),
  noteFrame: () => set({ lastSyncAt: Date.now() }),
}));

// React Query cache keys we invalidate on incoming events.
const TOPIC_INVALIDATIONS: Record<string, (qc: QcLike, missionId: number | null) => void> = {
  missions: (qc, mid) => {
    qc.invalidateQueries({ queryKey: ["missions"] });
    if (mid !== null) {
      qc.invalidateQueries({ queryKey: ["mission", mid] });
      qc.invalidateQueries({ queryKey: ["mission", mid, "pressure"] });
      qc.invalidateQueries({ queryKey: ["mission", mid, "deps"] });
      qc.invalidateQueries({ queryKey: ["mission", mid, "timeline"] });
      qc.invalidateQueries({ queryKey: ["mission", mid, "entities-grouped"] });
    }
  },
  execution: (qc, mid) => {
    qc.invalidateQueries({ queryKey: ["execution"] });
    if (mid !== null) {
      qc.invalidateQueries({ queryKey: ["mission", mid, "queue"] });
      qc.invalidateQueries({ queryKey: ["mission", mid, "pressure"] });
    }
  },
  approvals: (qc, mid) => {
    qc.invalidateQueries({ queryKey: ["execution"] });
    qc.invalidateQueries({ queryKey: ["pending-approvals"] });
    if (mid !== null) {
      qc.invalidateQueries({ queryKey: ["mission", mid, "pressure"] });
    }
  },
  graph: (qc, _mid) => {
    qc.invalidateQueries({ queryKey: ["relationships"] });
  },
  intelligence: (qc, _mid) => {
    qc.invalidateQueries({ queryKey: ["intel-top-signals"] });
  },
  presence: () => {
    // Presence updates go through a dedicated channel below; no RQ invalidation.
  },
};

interface QcLike {
  invalidateQueries: (opts: { queryKey: unknown[] }) => void;
}

let _bound = false;

export function bindRealtimeToQueryClient(qc: QcLike): () => void {
  if (_bound) return () => undefined;
  _bound = true;

  const ws = getWsClient();
  const store = useRealtimeStore;

  ws.setListeners({
    onStatusChange: (s) => {
      store.getState().setStatus(s);
    },
    onFrame: (frame: WSFrame) => {
      // Any inbound frame (event, presence, pong) proves the connection is live.
      store.getState().noteFrame();
      if (frame.type === "hello") {
        store.getState().setClientId(frame.client_id);
        return;
      }
      if (frame.type === "event") {
        const ev: OperationalEventRead = {
          id: frame.id,
          topic: frame.topic,
          event_type: frame.event_type,
          mission_id: frame.mission_id,
          entity_type: frame.entity_type,
          entity_id: frame.entity_id,
          actor: frame.actor,
          source: frame.source,
          severity: frame.severity,
          payload: frame.payload ?? null,
          created_at: frame.occurred_at ?? new Date().toISOString(),
        };
        store.getState().pushEvent(ev);
        const handler = TOPIC_INVALIDATIONS[frame.topic];
        if (handler) handler(qc, frame.mission_id ?? null);
        return;
      }
      if (frame.type === "presence_changed") {
        // Re-fetch presence for the affected mission. The component layer
        // owns the actual list — we only refresh.
        if (frame.mission_id !== null) {
          // We refresh via React Query so the presence-pill component
          // updates without bespoke wiring.
          qc.invalidateQueries({ queryKey: ["presence", frame.mission_id] });
        }
        qc.invalidateQueries({ queryKey: ["presence", "active"] });
      }
    },
    onResync: async (since) => {
      // On reconnect, replay missed events from /events/replay so the local
      // cache and store are coherent before the user notices a gap.
      try {
        const stream = await api.events({ since, limit: 200 });
        stream.items.forEach((ev) => {
          store.getState().pushEvent(ev);
          const handler = TOPIC_INVALIDATIONS[ev.topic];
          if (handler) handler(qc, ev.mission_id ?? null);
        });
      } catch {
        // best-effort
      }
    },
  });

  ws.connect();

  // Always subscribe to the "events" catch-all topic so the execution rail
  // stays alive across the whole shell. Per-page hooks subscribe to mission
  // scopes additively.
  ws.subscribe("missions");
  ws.subscribe("execution");
  ws.subscribe("approvals");
  ws.subscribe("intelligence");
  ws.subscribe("graph");
  ws.subscribe("presence");

  return () => {
    ws.close();
    _bound = false;
  };
}

/** Convenience hook for components that just need ws status. */
export function useWsStatus() {
  return useRealtimeStore((s) => s.status);
}

export function useRecentEvents(limit?: number) {
  const events = useRealtimeStore((s) => s.recentEvents);
  return limit ? events.slice(0, limit) : events;
}

/** Operational resilience snapshot — used by the awareness bar / banner. */
export function useResilienceSnapshot() {
  return useRealtimeStore(
    useShallow((s) => ({
      status: s.status,
      lastSyncAt: s.lastSyncAt,
      reconnectCount: s.reconnectCount,
      degradedSince: s.degradedSince,
      hasEverConnected: s.hasEverConnected,
    })),
  );
}
