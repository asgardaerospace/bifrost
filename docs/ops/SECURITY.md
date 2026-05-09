# Bifrost — Security Architecture

> Sprint 8 baseline. Additive enforcement, complete auditability,
> governance-first autonomy.

## Identity

* Email + password (bcrypt, length-clamped to bcrypt's 72-byte rule).
* JWT bearer tokens (HS256, configurable). Tokens carry `sub`, `iss`, `aud`,
  `iat`, `nbf`, `exp` and are validated on every protected route.
* Production refuses placeholder secrets and `JWT_SECRET_KEY` shorter than
  32 chars (validated at boot).
* Token rejection logs structured breadcrumbs (`expired` vs other JWT errors)
  without exposing token contents.

## Authorization

* Roles: `admin`, `executive`, `operator`, `analyst` (+ synthetic
  `anonymous`).
* Permission catalog is symbolic (`approval.decide`, `queue.execute`,
  `agent.run`, `policy.override`, `system.view`, `user.manage`,
  `data.export`).
* Routes ask for permissions, not roles, via
  `Depends(require_permission(...))`. The role→permission mapping is in
  `app/core/permissions.py:ROLES`.
* While `AUTH_ENFORCEMENT_ENABLED=false` (default), checks run in shadow
  mode: every decision is recorded in the audit log but a denial does not
  block the request. This is the migration runway — turn enforcement on
  once the audit log shows full coverage.

## Audit trail

Append-only, persisted via the existing `operational_events` table on a
reserved `audit` topic. Recorded actions (canonical names in
`app/services/audit.py`):

* `auth.login` / `auth.login_failed`
* `permission.deny`
* `approval.decide`
* `queue.execute`
* `agent.run` / `agent.autonomous_propose`
* `policy.override` / `policy.violation`
* `data.export`
* `user.create`

Every entry carries actor, outcome, target, mission_id (if any), and the
active trace metadata for cross-system correlation.

Read via `GET /api/v1/governance/audit?limit=50&action=...`.

## Rate limiting

Per-IP, per-route-prefix sliding window. Token-bucket-ish: `RATE_LIMIT_RPM`
total requests/minute, `RATE_LIMIT_BURST` cap over a 1-second sub-window.
Health and websocket-upgrade requests are exempt. Off by default; turn on
in production with `RATE_LIMIT_ENABLED=true`.

## Request validation

Pydantic v2 schemas at the edge. The middleware layer adds:
* request id correlation (so a malicious request is identifiable in logs);
* timeout-bounded responses;
* structured access logs for non-health paths.

## Secrets

* `.env.production.example` carries `CHANGE_ME` placeholders;
  `validate_env` refuses to boot if those reach production.
* No secrets in code, no secrets in image layers (`.dockerignore` excludes
  `.env*`).
* JWT secret rotation: change `JWT_SECRET_KEY`, restart backend. All
  existing tokens become invalid immediately (forces re-login).

## Governance enforcement

Execution policies live in `app/services/policy.py:EXECUTION_POLICIES`.
Each policy declares:

* `requires_approval` — must transit Approval ledger before execute.
* `min_confidence` — autonomy ledger floor for the action.
* `max_per_mission_per_hour` — rate ceiling per mission.
* `escalation_role` — role that owns out-of-band escalation.

Settings can globally tighten via:
* `GOVERNANCE_AUTONOMY_CONFIDENCE_FLOOR` — overrides per-policy floors when
  higher.
* `GOVERNANCE_MAX_PROPOSALS_PER_MISSION_PER_HOUR` — global default ceiling.

`policy.evaluate(...)` returns a `PolicyDecision` and emits both a
`governance` operational event and an audit row, so every autonomous
proposal is attributable and every workflow auditable.

## Threat model boundaries

**In scope today:**
* IDOR / role escalation via direct API access (RBAC + audit).
* Brute-force login (rate limit + audit).
* Replay / token tampering (iss/aud/nbf/exp validation).
* Runaway autonomy (confidence floor + per-mission rate ceiling +
  approval ledger).
* Silent privilege escalation (every permission decision audited).

**Out of scope today (deferred to Sprint 9+):**
* Per-row mission ACLs (we audit but don't yet enforce mission membership).
* Cross-org data isolation (single-org deployment assumption).
* Edge-level rate limiting (the in-process limiter is for defense in depth,
  not edge protection).
