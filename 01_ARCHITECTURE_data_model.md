# Bifrost Data Model

1. Structured normalized fields
2. Raw source content or summaries

Examples:
- Email body plus extracted next step
- Meeting notes plus structured outcome
- Document summary plus original file path

## Phase 1 Minimum Required Tables

The minimum set required to start implementation:

1. `investor_firms`
2. `investor_contacts`
3. `investor_opportunities`
4. `communications`
5. `meetings`
6. `notes`
7. `tasks`
8. `workflow_runs`
9. `approvals`
10. `documents`
11. `activity_events`
12. `tags`
13. `entity_tags`

## Data Integrity Rules

1. Every first-class record must have `created_at` and `updated_at`.
2. Every activity-producing action must create an `ActivityEvent`.
3. No communication may be marked `sent` without recording `sent_at`.
4. No approval may be marked `approved` or `rejected` without `reviewed_at`.
5. Every task completion must record `completed_at`.
6. Deletion should be soft delete where practical for business records.

## Future Schema Expansion

Later phases should add:

1. Supplier capability detail tables
2. Program readiness signal tables
3. Contact relationship mapping
4. Organization hierarchy support
5. Multi-user teams and permissions
6. Integration sync state tables
7. Launchbelt and Forge event streams

## Build Rules for Claude Code

1. Implement database tables using snake_case.
2. Keep service layer naming aligned to the entity names in this document.
3. Do not collapse `InvestorFirm`, `InvestorContact`, and `InvestorOpportunity` into one table.
4. Preserve generic attachable records using `entity_type` and `entity_id` where specified.
5. Add migrations incrementally, not by rewriting schema history.

## Definition of Success

The Phase 1 data model is successful when Bifrost can:

1. Represent investor firms, contacts, and active opportunities cleanly.
2. Record all major communications and meetings.
3. Track tasks, workflows, approvals, and activity events.
4. Support agent queries without relying on unstructured memory alone.
5. Expand into program and supplier domains without schema redesign.