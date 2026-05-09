# Bifrost — Observability

> Trace continuity, mission-aware metadata, structured logs to stdout.

## Components

```
HTTP request
   │  CorrelationMiddleware → x-request-id, x-trace-id
   ▼
service code (services/*.py)
   │  current_trace() → request_id, trace_id, mission_id, workflow_id
   ▼
events_service.publish()
   │  attaches _trace metadata to event payload
   ▼
operational_events row + websocket fanout
   │  subscribers see the same trace_id end-to-end
```

## Logs

Structured JSON to stdout. Every record carries:

```json
{
  "ts": "...", "level": "INFO", "logger": "bifrost.http",
  "msg": "http",
  "request_id": "...", "trace_id": "...",
  "mission_id": 12, "actor": "ops@example.com",
  "method": "POST", "path": "/api/v1/...", "status": 200, "elapsed_ms": 18.4
}
```

Configure with `LOG_LEVEL` (default INFO) and `LOG_FORMAT` (`json`|`text`).

## Request correlation

* Inbound `x-request-id` is honored if present (chain across services).
* If absent, a fresh UUID is generated.
* Echoed on every response as `x-request-id` and `x-trace-id`.
* Frontend generates a fresh `x-request-id` per fetch (see
  `frontend/lib/api.ts`) and attaches it to outbound requests.
* `ApiError.requestId` carries it back to the UI for correlated triage.

## Tracing (OpenTelemetry)

`app.core.observability.tracer.span(...)` is a façade. With
`OTEL_EXPORTER_OTLP_ENDPOINT` set and `opentelemetry-api` installed, spans
are emitted through OTel; otherwise they degrade to structured log
breadcrumbs and timer histograms. No code change needed to enable.

## Metrics

In-process registry exposed at `GET /api/v1/observability/metrics`:

* `counters` — `http.requests`, `http.status.*`, `http.rate_limited`,
  `events.published.*`, `policy.allow.*`, `policy.deny.*`,
  `permissions.allow.*`, `permissions.deny.*`,
  `reliability.retry.*`, `reliability.breaker.*`,
  `audit.*`.
* `gauges` — `pubsub.connections`.
* `timers` — request latency, span timings (avg / p50 / p95 / max).

Operators can wire a Prometheus scrape against this endpoint, or pull on a
schedule into a TSDB of choice.

## System snapshot

`GET /api/v1/observability/system` (admin-gated once enforcement is on)
returns environment, pubsub state (redis attached y/n, connection count),
rate-limit config, governance ceilings, and counters.

## Correlating an incident

1. Operator surfaces a failed action — copy the request id from the toast
   or browser devtools.
2. `kubectl logs / docker logs` filtered on that request_id returns every
   record from the request including service-level breadcrumbs.
3. The same trace_id appears on the corresponding `operational_events` row
   (in `payload._trace`) — query DB or `/events?...` to see what fired
   downstream.
