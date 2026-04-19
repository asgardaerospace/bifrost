# Bifrost Command Console Specification

## Purpose

The command console is the primary executive interface for Bifrost. It allows the user to query the system, request analysis, generate drafts, and initiate workflows using structured natural language commands.

This is not a chat interface. It is a **controlled command system** for decision-making and execution.

---

## Core Objectives

1. Provide a single interface to operate the business
2. Translate natural language into structured system actions
3. Maintain strict separation between:
   - information
   - recommendations
   - drafts
   - executed actions
4. Enable fast execution with full traceability
5. Reduce navigation across multiple tools

---

## Command Model

Every command must map to one of six types:

### 1. READ
Retrieve information

Examples:
- Show investor pipeline
- Show overdue follow-ups

---

### 2. ANALYZE
Rank, score, or evaluate

Examples:
- Rank investors most likely to close
- Identify stale opportunities

---

### 3. DRAFT
Generate content

Examples:
- Draft a follow-up email
- Create investor update

---

### 4. PLAN
Recommend actions

Examples:
- What should I focus on today
- What are top priorities this week

---

### 5. EXECUTE
Trigger workflows (requires control + approval)

Examples:
- Create follow-up tasks
- Generate outreach drafts

---

### 6. REVIEW
Inspect system state

Examples:
- Show pending approvals
- Show blocked workflows

---

## Command Processing Flow

### Step 1: Input
User enters command

### Step 2: Classification
System assigns command type

### Step 3: Entity Resolution
System identifies:
- investor
- program
- contact
- etc.

### Step 4: Validation
Check:
- sufficient data
- allowed action

### Step 5: Routing
Send to:
- data service
- agent
- workflow engine

### Step 6: Response
Return structured output

### Step 7: Logging
Store:
- command
- classification
- result
- linked entities

---

## Output Types

### Summary Output
- headline
- key insights
- supporting data
- next actions

---

### Ranked Output
- ordered list
- scoring logic
- reasoning

---

### Draft Output
- subject/title
- body
- target entity
- status (draft)

---

### Workflow Output
- workflow type
- actions created
- approval required
- status

---

### Review Output
- approvals
- risks
- blocked items

---

## UI Requirements

### Command Input
- text input
- submit action
- recent commands

---

### Response Panel
Must support:
- summaries
- lists
- drafts
- actions

---

### Context Panel
Display:
- detected entities
- command type
- related records

---

### Action Controls
Allow:
- save draft
- create task
- request approval
- open record

---

## Safety Rules

1. No direct execution of external actions from raw commands
2. All outbound communication requires approval
3. Draft ≠ sent
4. No silent state changes
5. Ask for clarification if entity is ambiguous

---

## Entity Resolution Rules

Priority:
1. exact match
2. known alias
3. recent context
4. fuzzy match

If unclear:
→ return options, do not guess

---

## Logging Requirements

Log every command:
- input
- classification
- entities
- output type
- actions created
- duration

---

## Phase 1 Requirements

1. Command input UI
2. Command classification
3. Investor commands fully supported
4. Draft generation
5. Workflow triggering with approval
6. Structured outputs
7. Full logging

---

## Build Constraints

1. Do NOT build a chatbot
2. Use typed responses, not free text blobs
3. Separate parsing from execution
4. Keep workflows explicit
5. Preserve auditability

---

## Definition of Success

The command console is successful when the user can:

1. Ask for investor status
2. Get ranked priorities
3. Generate drafts
4. Trigger workflows
5. Review approvals

All from one interface, with full control and traceability.