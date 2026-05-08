"use client";

/**
 * Reconnect-safe WebSocket client for the Bifrost realtime layer.
 *
 * Sprint 2 contract:
 *   - One persistent connection per browser tab.
 *   - Reconnect with exponential backoff (1s → 30s, capped) on close.
 *   - Heartbeat every 15s; server replies with `pong`.
 *   - Topic + mission_id subscriptions are persistent across reconnects.
 *   - On reconnect, replay missed events via /events/replay?since=<lastId>
 *     so subscribers never miss a state change.
 *
 * The client is framework-agnostic; the React layer in `lib/realtime-store.ts`
 * binds it into a Zustand store and into React Query cache invalidation.
 */

import { API_BASE_URL } from "./api";
import type { WSFrame } from "@/types/api";

export type WSStatus = "idle" | "connecting" | "open" | "closed";

export interface SubscriptionKey {
  topic: string;
  missionId: number | null;
}

export interface BifrostWSClient {
  connect(): void;
  close(): void;
  subscribe(topic: string, missionId?: number | null): void;
  unsubscribe(topic: string, missionId?: number | null): void;
  setMissionFocus(missionId: number | null, displayName?: string): void;
  status(): WSStatus;
  clientId(): string;
  setListeners(listeners: WSListeners): void;
}

export interface WSListeners {
  onStatusChange?: (status: WSStatus) => void;
  onFrame?: (frame: WSFrame) => void;
  /** Called when reconnecting — handler should replay events since lastEventId. */
  onResync?: (lastEventId: number) => void;
}

const HEARTBEAT_MS = 15_000;
const BACKOFF_BASE_MS = 1_000;
const BACKOFF_CAP_MS = 30_000;

function deriveWsUrl(): string {
  // API_BASE_URL ends with /api/v1 (no trailing slash). Replace http(s) →
  // ws(s) and append /ws.
  const base = API_BASE_URL || "/api/v1";
  if (base.startsWith("ws://") || base.startsWith("wss://")) {
    return base + "/ws";
  }
  if (base.startsWith("http://")) {
    return "ws://" + base.slice("http://".length) + "/ws";
  }
  if (base.startsWith("https://")) {
    return "wss://" + base.slice("https://".length) + "/ws";
  }
  // Relative — derive from window.location.
  if (typeof window !== "undefined") {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.host}${base}/ws`;
  }
  return base + "/ws";
}

function genClientId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `c-${Math.random().toString(36).slice(2)}-${Date.now().toString(36)}`;
}

class BifrostWSClientImpl implements BifrostWSClient {
  private ws: WebSocket | null = null;
  private _status: WSStatus = "idle";
  private _clientId: string = genClientId();
  private subs: Map<string, SubscriptionKey> = new Map();
  private missionFocus: number | null = null;
  private displayName: string | undefined;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts = 0;
  private listeners: WSListeners = {};
  private explicitlyClosed = false;
  private lastEventId = 0;

  setListeners(listeners: WSListeners) {
    this.listeners = listeners;
  }

  status(): WSStatus {
    return this._status;
  }

  clientId(): string {
    return this._clientId;
  }

  connect() {
    if (this._status === "open" || this._status === "connecting") return;
    this.explicitlyClosed = false;
    this.openSocket();
  }

  close() {
    this.explicitlyClosed = true;
    this.clearTimers();
    if (this.ws) {
      try {
        this.ws.close();
      } catch {
        // ignore
      }
      this.ws = null;
    }
    this.setStatus("closed");
  }

  subscribe(topic: string, missionId: number | null = null) {
    const key = subKey(topic, missionId);
    this.subs.set(key, { topic, missionId });
    this.send({ action: "subscribe", topic, mission_id: missionId });
  }

  unsubscribe(topic: string, missionId: number | null = null) {
    const key = subKey(topic, missionId);
    this.subs.delete(key);
    this.send({ action: "unsubscribe", topic, mission_id: missionId });
  }

  setMissionFocus(missionId: number | null, displayName?: string) {
    this.missionFocus = missionId;
    if (displayName !== undefined) this.displayName = displayName;
    this.send({
      action: "presence",
      mission_id: missionId,
      display_name: this.displayName,
      client_id: this._clientId,
    });
  }

  // -- internals -------------------------------------------------------

  private openSocket() {
    this.setStatus("connecting");
    const url = `${deriveWsUrl()}?client_id=${encodeURIComponent(this._clientId)}`;
    let ws: WebSocket;
    try {
      ws = new WebSocket(url);
    } catch (err) {
      this.scheduleReconnect();
      return;
    }
    this.ws = ws;

    ws.onopen = () => {
      this.setStatus("open");
      this.reconnectAttempts = 0;

      // Replay missed events first, then re-establish subscriptions.
      if (this.lastEventId > 0 && this.listeners.onResync) {
        this.listeners.onResync(this.lastEventId);
      }
      this.subs.forEach(({ topic, missionId }) => {
        this.send({ action: "subscribe", topic, mission_id: missionId });
      });
      if (this.missionFocus !== null) {
        this.send({
          action: "presence",
          mission_id: this.missionFocus,
          display_name: this.displayName,
          client_id: this._clientId,
        });
      }
      this.startHeartbeat();
    };

    ws.onmessage = (e) => {
      let frame: WSFrame | null = null;
      try {
        frame = JSON.parse(e.data) as WSFrame;
      } catch {
        return;
      }
      if (!frame) return;
      if (frame.type === "event" && typeof frame.id === "number") {
        if (frame.id > this.lastEventId) this.lastEventId = frame.id;
      }
      this.listeners.onFrame?.(frame);
    };

    ws.onclose = () => {
      this.stopHeartbeat();
      this.ws = null;
      if (this.explicitlyClosed) {
        this.setStatus("closed");
        return;
      }
      this.scheduleReconnect();
    };

    ws.onerror = () => {
      // Let onclose handle reconnect.
    };
  }

  private send(payload: object) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(payload));
    }
  }

  private startHeartbeat() {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      this.send({ action: "heartbeat" });
    }, HEARTBEAT_MS);
  }

  private stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private scheduleReconnect() {
    this.setStatus("closed");
    if (this.explicitlyClosed) return;
    if (this.reconnectTimer) return;

    const delay = Math.min(
      BACKOFF_CAP_MS,
      BACKOFF_BASE_MS * 2 ** Math.min(this.reconnectAttempts, 6),
    );
    this.reconnectAttempts += 1;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.openSocket();
    }, delay);
  }

  private clearTimers() {
    this.stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private setStatus(s: WSStatus) {
    if (this._status === s) return;
    this._status = s;
    this.listeners.onStatusChange?.(s);
  }
}

function subKey(topic: string, missionId: number | null): string {
  return `${topic}::${missionId ?? "*"}`;
}

let _client: BifrostWSClient | null = null;

export function getWsClient(): BifrostWSClient {
  if (_client === null) _client = new BifrostWSClientImpl();
  return _client;
}
