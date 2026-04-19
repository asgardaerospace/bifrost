# Bifrost Phase 1 Build Plan

## Purpose

This document defines the exact implementation sequence for Bifrost Phase 1.

Its purpose is to:
- eliminate ambiguity during development
- minimize wasted Claude credits
- enforce disciplined execution order
- ensure the system is built as an operational tool, not a prototype

---

## Phase 1 Objective

Deliver a working internal system that allows Asgard leadership to:

1. Manage investor pipeline in structured form
2. View real-time status across all opportunities
3. Use command interface to query and operate
4. Generate follow-up drafts and meeting briefs
5. Execute workflows with approval control
6. Track activity, tasks, and decisions

---

## Phase 1 Scope

### Included

- Investor data model and CRUD
- Workflow and approval system
- Investor agent (core functions)
- Command console (limited scope)
- Dashboard (basic visibility)
- Activity logging

---

### Excluded

- Supplier system
- Full program acquisition system
- Autonomous execution
- Complex integrations
- Multi-tenant architecture

---

## Build Philosophy

1. Build system of record first
2. Build workflows second
3. Add intelligence third
4. Add UI last
5. Keep everything observable
6. Avoid overbuilding

---

## Implementation Sequence

---

### Phase 1A — Foundation

**Goal:** Create working backend + repo structure

**Tasks:**
1. Initialize repo structure
2. Setup backend (FastAPI)
3. Setup frontend (Next.js)
4. Configure environment variables
5. Setup linting and formatting

**Output:**
- Running backend server
- Running frontend app
- Clean repo structure

---

### Phase 1B — Data Layer

**Goal:** Implement system of record

**Tasks:**
1. Setup PostgreSQL
2. Configure SQLAlchemy models
3. Create Alembic migrations
4. Implement core tables:
   - investor_firms
   - investor_contacts
   - investor_opportunities
   - communications
   - meetings
   - tasks
   - approvals
   - workflow_runs
   - activity_events

**Output:**
- Working database schema
- Migration system functional

---

### Phase 1C — Core APIs

**Goal:** Make data usable

**Tasks:**
1. CRUD endpoints for:
   - firms
   - contacts
   - opportunities
2. Timeline endpoint
3. Task creation endpoints
4. Activity logging integration

**Output:**
- Full investor data interaction via API

---

### Phase 1D — Workflow Engine

**Goal:** Control execution layer

**Tasks:**
1. Implement workflow_run logic
2. Implement approval system
3. Implement communication draft creation
4. Implement approval → send pathway
5. Enforce audit logging

**Output:**
- Controlled execution system
- Approval-based actions

---

### Phase 1E — Investor Agent

**Goal:** Add intelligence layer

**Tasks:**
1. Investor summary service
2. Investor prioritization logic
3. Draft email generator
4. Meeting brief generator
5. Logging of all agent outputs

**Output:**
- Functional investor agent

---

### Phase 1F — Command Console

**Goal:** Create executive interface

**Tasks:**
1. Command input UI
2. Command classification endpoint
3. Routing logic
4. Response rendering
5. Action triggers

**Output:**
- Usable command interface

---

### Phase 1G — Dashboard

**Goal:** Passive visibility layer

**Tasks:**
1. Pipeline view
2. Overdue follow-ups
3. Pending approvals
4. Activity feed
5. Upcoming meetings

**Output:**
- Executive overview screen

---

### Phase 1H — Integration + Polish

**Goal:** Make system usable end-to-end

**Tasks:**
1. Email integration (approved sends only)
2. Error handling
3. Edge case handling
4. Basic testing
5. Internal deployment setup

**Output:**
- Internal release-ready system

---

## Task Strategy for Claude

### Good Tasks

- Create SQLAlchemy models for investor tables
- Build API endpoint for pipeline summary
- Implement approval workflow logic
- Build command classification service

---

### Bad Tasks

- Build entire backend
- Design full system automatically
- Create “AI system” broadly

---

## Prompt Pattern

Always structure prompts like this:

1. Reference document
2. Define task
3. Define constraints
4. Define output

---

### Example Prompt

```text
Using 01_ARCHITECTURE/data_model.md and 04_WORKFLOWS/investor_workflow.md, implement the backend service for follow-up draft creation. Create communication records, workflow_run, and activity_event. Do not send emails.