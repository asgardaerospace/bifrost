# Bifrost — Realtime Architecture

> Persist-then-broadcast event bus, reconnect-safe websocket clients,
> resync via replay, calm degraded states.

## Topology

```
service code
   │  events_service.publish(db, payload)
   │     ├─ persist OperationalEvent row
   │     └─ pubsub_manager.publish_sync(topic, mission_id, message)
   ▼
PubSubManager
   │  if REDIS_URL → PUBLISH bifrost:<topic> (cross-process)
   │                  per-process subscriber receives → fan to local sockets
   │  else        → fan to local sockets directly
   ▼
WebSocket clients
   │  filter (topic, mission_id?)
   │  send_json(...) with 5s timeout (slow consumers dropped)
   ▼
Frontend WS client (lib/ws-client.ts)
   │  exponential backoff 1s → 30s on close
   │  heartbeat every 15s
   │  on reconnect: replay missed events via /events/replay?since=<lastId>
```

## Doctrine

* Persistence first, broadcast second — durable record exists before fanout.
* Cursors are monotonic event ids; clients reconcile gaps via replay.
* Topics are the canonical bus axis: `missions`, `intelligence`, `execution`,
  `graph`, `memory`, `agents`, `presence`, `approvals`, `events`, `audit`,
  `governance`.
* Subscriptions are persistent across reconnects (re-sent automatically).
* No event storms — the server drops slow consumers via send timeout rather
  than buffering unboundedly.

## Frontend resilience

* `getWsClient()` returns a singleton with backoff state.
* Status surface via `useWsStatus()`; resilience snapshot via
  `useResilienceSnapshot()` (last sync, reconnect count, degraded since).
* `<ResilienceBanner />` renders **only** when degraded > 8s (avoids flicker
  on quick blips) or when no frame has arrived in >60s while open.
* Failure presentation is calm: a thin amber strip, no modal, no sound.

## Multi-worker

When `REDIS_URL` is set:
* Each worker subscribes to `bifrost:*` via Redis pub/sub.
* Local fanout still happens — the publisher path is short-circuited so a
  given message isn't delivered twice to the same socket.

When unset:
* Single-process fanout only. Multiple workers will fragment the event
  ribbon. Single-worker prod is fine for small deployments; otherwise wire
  Redis.

## Auth (websockets)

* `?token=<jwt>` query param. When `auth_enforcement_enabled=true`, missing
  or invalid token results in `close(code=4401)`.
* Anonymous connections allowed in dev (matches HTTP route behavior).

## Replay endpoint

```
GET /api/v1/events/replay?since=<id>&topics=missions&topics=execution&limit=500
```

Idempotent, monotonic, bounded. Frontend calls this on every reconnect to
fill the gap before the user notices. Server returns the cursor of the last
delivered row so the client can iterate if more remain.
