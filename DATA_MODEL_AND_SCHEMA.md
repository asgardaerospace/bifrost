# DATA_MODEL_AND_SCHEMA.md

# Bifrost Data Model and Schema
## Canonical Data Architecture for Asgard Aerospace

Version: 1.0  
System: Bifrost OS  
Organization: Asgard Aerospace

---

# 1. Purpose

The Data Model and Schema defines the canonical backend structure for Bifrost.

This document governs:

- core entities
- relational schemas
- mission linkages
- operational graph relationships
- event structures
- memory structures
- intelligence objects
- execution objects
- approval objects
- vector and semantic retrieval structures

This document prevents:

- duplicate entities
- inconsistent schemas
- disconnected graph relationships
- fragmented workflow state
- weak AI grounding
- untraceable autonomy
- operational data drift

Bifrost is not a collection of isolated tables.

Bifrost is a mission-aware operational graph.

---

# 2. Core Data Philosophy

## Canonical Entities First

Every major object must exist as a canonical entity.

Examples:

- Mission
- Investor
- Account
- Program
- Supplier
- Intelligence Signal
- Action
- Approval
- Risk
- Event
- Memory Record

---

## Relationships Are First-Class

Relationships must be stored and queried directly.

Relationships define:

- dependencies
- funding relevance
- supplier support
- mission impact
- operational pressure
- strategic influence

---

## Events Preserve Operational Truth

Every meaningful change should generate an event.

Events support:

- auditability
- realtime updates
- graph propagation
- organizational memory
- autonomy reasoning

---

## Mission Linkage Is Required

All major records should link directly or indirectly to a mission.

If a record has no mission relevance, it remains ambient until relevance emerges.

---

# 3. Core Entity Tables

---

# 3.1 missions

## Purpose

Primary strategic execution object.

```yaml
missions:
  id: uuid
  name: text
  description: text
  mission_type: enum
  status: enum
  owner_user_id: uuid nullable
  strategic_value_score: integer
  urgency_score: integer
  risk_score: integer
  health_score: integer
  pressure_score: integer
  start_date: datetime nullable
  target_date: datetime nullable
  created_at: datetime
  updated_at: datetime
```

## Mission Status

```yaml
proposed
active
focused
escalated
blocked
stabilized
completed
archived
```

## Mission Types

```yaml
capital
market
program
supplier
intelligence
recovery
executive
```

---

# 3.2 entities

## Purpose

Optional unified registry for graph-compatible entities.

```yaml
entities:
  id: uuid
  entity_type: text
  entity_id: uuid
  display_name: text
  source_system: text
  canonical_key: text
  created_at: datetime
  updated_at: datetime
```

Use this only if it improves graph and search consistency.

---

# 3.3 contacts

## Purpose

Canonical human relationship object.

```yaml
contacts:
  id: uuid
  first_name: text
  last_name: text
  full_name: text
  title: text nullable
  email: text nullable
  phone: text nullable
  linkedin_url: text nullable
  organization_name: text nullable
  relationship_strength: integer
  contact_type: enum
  source_system: text nullable
  external_id: text nullable
  created_at: datetime
  updated_at: datetime
```

---

# 3.4 investors

## Purpose

Canonical investor organization object.

```yaml
investors:
  id: uuid
  name: text
  investor_type: enum
  focus_areas: jsonb
  stage_preference: text nullable
  geographic_focus: jsonb
  relationship_strength: integer
  engagement_status: enum
  owner_user_id: uuid nullable
  last_interaction_at: datetime nullable
  next_action_at: datetime nullable
  source_system: text nullable
  external_id: text nullable
  created_at: datetime
  updated_at: datetime
```

---

# 3.5 accounts

## Purpose

Market-facing company, partner, customer, or target account.

```yaml
accounts:
  id: uuid
  name: text
  account_type: enum
  sector: text nullable
  region: text nullable
  website: text nullable
  relationship_status: enum
  strategic_value_score: integer
  owner_user_id: uuid nullable
  created_at: datetime
  updated_at: datetime
```

---

# 3.6 programs

## Purpose

Execution object for business, manufacturing, technical, or customer programs.

```yaml
programs:
  id: uuid
  name: text
  description: text
  program_type: enum
  account_id: uuid nullable
  status: enum
  phase: text nullable
  estimated_value: numeric nullable
  probability_score: integer
  strategic_value_score: integer
  risk_score: integer
  owner_user_id: uuid nullable
  next_step: text nullable
  next_step_due_at: datetime nullable
  created_at: datetime
  updated_at: datetime
```

---

# 3.7 suppliers

## Purpose

Manufacturing, material, capability, or service partner.

```yaml
suppliers:
  id: uuid
  name: text
  supplier_type: text
  region: text nullable
  country: text nullable
  website: text nullable
  onboarding_status: enum
  preferred_partner_score: integer
  risk_score: integer
  capacity_score: integer
  compliance_status: enum
  notes: text nullable
  created_at: datetime
  updated_at: datetime
```

---

# 3.8 opportunities

## Purpose

General opportunity object across market, capital, and program domains.

```yaml
opportunities:
  id: uuid
  name: text
  opportunity_type: enum
  related_entity_type: text
  related_entity_id: uuid
  mission_id: uuid nullable
  status: enum
  stage: text nullable
  estimated_value: numeric nullable
  probability_score: integer
  strategic_value_score: integer
  next_step: text nullable
  next_step_due_at: datetime nullable
  owner_user_id: uuid nullable
  created_at: datetime
  updated_at: datetime
```

---

# 4. Mission Relationship Tables

---

# 4.1 mission_entities

## Purpose

Connect missions to all related entities.

```yaml
mission_entities:
  id: uuid
  mission_id: uuid
  entity_type: text
  entity_id: uuid
  relevance_score: integer
  relationship_type: text
  created_at: datetime
  updated_at: datetime
```

---

# 4.2 relationships

## Purpose

General operational relationship graph edge.

```yaml
relationships:
  id: uuid
  source_entity_type: text
  source_entity_id: uuid
  target_entity_type: text
  target_entity_id: uuid
  relationship_type: enum
  strength_score: integer
  confidence_score: integer
  mission_id: uuid nullable
  metadata_json: jsonb
  created_at: datetime
  updated_at: datetime
```

## Relationship Types

```yaml
depends_on
blocks
supports
funds
supplies
owns
affects
influences
participates_in
relates_to
mitigates
escalates_to
connected_to
```

---

# 5. Intelligence Tables

---

# 5.1 intelligence_signals

## Purpose

Structured external or internal signal object.

```yaml
intelligence_signals:
  id: uuid
  title: text
  source: text
  url: text nullable
  signal_type: enum
  category: text
  region: text nullable
  summary: text
  published_at: datetime nullable
  confidence_score: integer
  urgency_score: integer
  strategic_relevance_score: integer
  mission_relevance_score: integer
  cross_system_impact_score: integer
  created_at: datetime
  updated_at: datetime
```

---

# 5.2 intelligence_entities

## Purpose

Entities mentioned or affected by intelligence signals.

```yaml
intelligence_entities:
  id: uuid
  intelligence_signal_id: uuid
  entity_type: text
  entity_id: uuid nullable
  entity_name: text
  role: text nullable
  confidence_score: integer
  created_at: datetime
```

---

# 5.3 intelligence_actions

## Purpose

Recommended actions generated from signals.

```yaml
intelligence_actions:
  id: uuid
  intelligence_signal_id: uuid
  action_type: text
  title: text
  description: text
  status: enum
  priority_score: integer
  related_entity_type: text nullable
  related_entity_id: uuid nullable
  mission_id: uuid nullable
  created_at: datetime
  updated_at: datetime
```

---

# 6. Execution Tables

---

# 6.1 actions

## Purpose

Canonical operational action object.

```yaml
actions:
  id: uuid
  title: text
  description: text nullable
  action_type: text
  domain: text
  status: enum
  priority_score: integer
  pressure_score: integer
  mission_id: uuid nullable
  related_entity_type: text nullable
  related_entity_id: uuid nullable
  assigned_to_user_id: uuid nullable
  due_at: datetime nullable
  approval_required: boolean
  created_at: datetime
  updated_at: datetime
```

## Action Status

```yaml
proposed
queued
in_progress
blocked
pending_approval
completed
failed
snoozed
archived
```

---

# 6.2 approvals

## Purpose

Governed authorization records.

```yaml
approvals:
  id: uuid
  approval_type: text
  status: enum
  requested_by_user_id: uuid nullable
  assigned_approver_user_id: uuid nullable
  related_entity_type: text
  related_entity_id: uuid
  action_id: uuid nullable
  request_summary: text
  decision_summary: text nullable
  requested_at: datetime
  resolved_at: datetime nullable
  created_at: datetime
  updated_at: datetime
```

---

# 6.3 execution_queue_items

## Purpose

Queue surface for active work.

```yaml
execution_queue_items:
  id: uuid
  action_id: uuid nullable
  mission_id: uuid nullable
  domain: text
  title: text
  description: text
  priority_score: integer
  pressure_score: integer
  urgency_score: integer
  status: enum
  source_type: text
  source_id: uuid nullable
  due_at: datetime nullable
  owner_user_id: uuid nullable
  created_at: datetime
  updated_at: datetime
```

---

# 7. Autonomy Tables

---

# 7.1 autonomy_operations

## Purpose

Records autonomous recommendations and proposed execution.

```yaml
autonomy_operations:
  id: uuid
  operation_type: text
  status: enum
  risk_level: enum
  confidence_score: integer
  approval_required: boolean
  mission_id: uuid nullable
  related_entity_type: text nullable
  related_entity_id: uuid nullable
  trigger_event_id: uuid nullable
  reasoning_summary: text
  payload_json: jsonb
  execution_result_json: jsonb nullable
  created_at: datetime
  updated_at: datetime
```

---

# 7.2 proposed_actions

## Purpose

First-class autonomous or system-generated action proposals.

```yaml
proposed_actions:
  id: uuid
  trigger_event_id: uuid nullable
  action_type: text
  domain: text
  title: text
  description: text
  related_entity_type: text nullable
  related_entity_id: uuid nullable
  payload_json: jsonb
  risk_level: enum
  confidence_score: integer
  approval_required: boolean
  execution_status: enum
  execution_result: text nullable
  created_at: datetime
  updated_at: datetime
```

---

# 8. Event Tables

---

# 8.1 operational_events

## Purpose

Immutable operational event stream.

```yaml
operational_events:
  id: uuid
  event_type: text
  source_system: text
  entity_type: text nullable
  entity_id: uuid nullable
  mission_id: uuid nullable
  priority: text
  urgency_score: integer
  relevance_score: integer
  confidence_score: integer
  payload_json: jsonb
  created_at: datetime
  propagation_state: text
  visibility_scope: text
```

---

# 8.2 activity_events

## Purpose

Human-readable audit and activity timeline.

```yaml
activity_events:
  id: uuid
  entity_type: text
  entity_id: uuid
  event_type: text
  summary: text
  details_json: jsonb
  actor_type: text
  actor_id: uuid nullable
  created_at: datetime
```

---

# 9. Memory Tables

---

# 9.1 memory_records

## Purpose

Structured organizational memory object.

```yaml
memory_records:
  id: uuid
  memory_type: text
  title: text
  summary: text
  source_entity_type: text nullable
  source_entity_id: uuid nullable
  mission_id: uuid nullable
  importance_score: integer
  confidence_score: integer
  visibility_scope: text
  created_at: datetime
  updated_at: datetime
```

---

# 9.2 semantic_chunks

## Purpose

Vector-searchable text or document chunks.

```yaml
semantic_chunks:
  id: uuid
  source_type: text
  source_id: uuid
  chunk_text: text
  embedding: vector nullable
  metadata_json: jsonb
  mission_id: uuid nullable
  created_at: datetime
  updated_at: datetime
```

---

# 10. Communication Tables

---

# 10.1 communications

## Purpose

Drafted, sent, or reviewed communication artifacts.

```yaml
communications:
  id: uuid
  communication_type: text
  status: enum
  subject: text nullable
  body: text
  source_system: text nullable
  source_external_id: text nullable
  related_entity_type: text nullable
  related_entity_id: uuid nullable
  mission_id: uuid nullable
  approval_id: uuid nullable
  sent_at: datetime nullable
  created_at: datetime
  updated_at: datetime
```

---

# 11. Risk Tables

---

# 11.1 risks

## Purpose

Operational or strategic risk object.

```yaml
risks:
  id: uuid
  name: text
  description: text
  risk_type: text
  severity: enum
  likelihood_score: integer
  impact_score: integer
  status: enum
  mission_id: uuid nullable
  related_entity_type: text nullable
  related_entity_id: uuid nullable
  mitigation_plan: text nullable
  owner_user_id: uuid nullable
  created_at: datetime
  updated_at: datetime
```

---

# 12. User and Role Tables

---

# 12.1 users

```yaml
users:
  id: uuid
  email: text
  full_name: text
  role: text
  status: enum
  created_at: datetime
  updated_at: datetime
```

---

# 12.2 user_roles

```yaml
user_roles:
  id: uuid
  user_id: uuid
  role_name: text
  trust_zone: text nullable
  created_at: datetime
```

---

# 13. Schema Rules

## UUID Primary Keys

All major tables use UUID primary keys.

---

## JSONB For Flexible Payloads

Use JSONB only for:

- provider payloads
- metadata
- execution results
- external sync state
- AI reasoning traces

Do not use JSONB as a replacement for canonical schema.

---

## Soft Deletion

Strategic records should not be hard deleted.

Use:

```yaml
archived_at
deleted_at
status
```

where appropriate.

---

## Timestamps

Every operational table must include:

```yaml
created_at
updated_at
```

Immutable event tables may omit updated_at.

---

# 14. AI Grounding Rules

AI systems must use:

- structured tables first
- semantic retrieval second
- LLM reasoning third

AI may not invent:

- records
- relationships
- mission states
- approvals
- operational history

---

# 15. Final Doctrine

## Core Principles

### Schema Creates Trust
Operational intelligence depends on structure.

### Relationships Create Meaning
The graph is built from canonical relationships.

### Events Preserve Truth
Every change should remain traceable.

### Missions Organize Data
Strategic objectives anchor the model.

### Memory Enables Continuity
The OS should remember over time.

### AI Must Be Grounded
Reasoning depends on verifiable data.

---

# Final Objective

The Bifrost Data Model exists to create:

- canonical operational truth
- mission-aware intelligence
- graph-based relationship reasoning
- governed autonomy
- persistent organizational memory
- aerospace-grade execution reliability