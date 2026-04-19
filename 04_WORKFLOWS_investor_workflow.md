# Investor Workflow Specification

## Purpose

This document defines the structured investor execution workflow for Bifrost Phase 1.

The goal is to create a **repeatable, controlled system** for managing investor relationships, progressing deals, and executing outreach with discipline and traceability.

This workflow must be implemented in code, not inferred dynamically.

---

## Core Objective

Enable Asgard to:

1. Track investor opportunities end-to-end
2. Maintain momentum across all deals
3. Generate structured follow-ups
4. Enforce approval before outbound actions
5. Preserve full execution history

---

## Workflow Stages

Each investor opportunity must exist in one of the following stages:

### 1. IDENTIFIED
Investor is known but not yet qualified

**Actions:**
- Create InvestorFirm
- Create InvestorOpportunity
- Add notes and context

---

### 2. QUALIFIED
Investor meets basic criteria

**Criteria:**
- Thesis alignment
- Check size fit
- Strategic relevance
- Contact access

**Actions:**
- Update fit_score
- Add qualification notes
- Create next-step task

---

### 3. CONTACTED
Initial outreach sent or intro made

**Actions:**
- Create communication draft
- Route for approval
- Send after approval
- Log interaction
- Create follow-up task

---

### 4. INTRO_CALL
Initial meeting completed or scheduled

**Actions:**
- Create meeting record
- Generate meeting brief
- Log notes and outcome
- Define next step

---

### 5. DILIGENCE
Investor actively evaluating

**Actions:**
- Track questions
- Log communications
- Create response tasks
- Track blockers

---

### 6. PARTNER_MEETING
Final-stage discussions

**Actions:**
- Generate partner brief
- Track objections
- Prepare materials
- Define decision timeline

---

### 7. DECISION
Outcome reached

**Possible States:**
- term_sheet
- closed_won
- closed_lost
- deferred

**Actions:**
- Record outcome
- Close or transition tasks
- Log final notes

---

## Core Sub-Workflows

---

### A. Follow-Up Draft Workflow

**Trigger:**
- User request
- Overdue follow-up detected

**Steps:**
1. Load investor + contact
2. Load recent communication
3. Load last meeting notes
4. Determine objective
5. Generate draft
6. Save as Communication (status = draft)
7. Log activity

**Output:**
- Draft email ready for review

---

### B. Send Approval Workflow

**Trigger:**
User chooses to send draft

**Steps:**
1. Validate draft exists
2. Create Approval record
3. Set communication to pending_approval
4. Wait for approval
5. On approval → send email
6. Update status to sent
7. Log activity

**Rule:**
No email is ever sent without approval

---

### C. Weekly Review Workflow

**Trigger:**
- Manual request
- Scheduled execution

**Steps:**
1. Load all active opportunities
2. Group by stage
3. Identify:
   - stale deals
   - overdue follow-ups
   - high-priority deals
4. Rank opportunities
5. Output action plan
6. Offer task/draft creation

---

### D. Meeting Prep Workflow

**Trigger:**
User requests meeting brief

**Steps:**
1. Load investor + contact
2. Load notes and history
3. Summarize:
   - stage
   - fit
   - risks
4. Generate:
   - talking points
   - desired outcome
5. Save as note or document
6. Log activity

---

## Priority Logic

Investor prioritization should consider:

1. stage
2. last interaction date
3. next step due date
4. probability_score
5. strategic_value_score
6. fit_score
7. presence of blockers

---

## SLA Guidance

Internal discipline targets:

- No opportunity without next step
- No follow-up overdue > 7 days
- Diligence deals reviewed weekly
- Partner meetings always prioritized

---

## Data Hygiene Rules

1. Every opportunity must have an owner
2. Every active opportunity must have next_step
3. Every meeting must have outcome notes
4. Every sent communication must be logged
5. Every workflow must create ActivityEvent

---

## Dashboard Requirements

System must support:

- Opportunities by stage
- Overdue follow-ups
- Missing next steps
- Inactive deals (>21 days)
- Pending approvals
- Upcoming meetings

---

## Failure Handling

If workflow cannot proceed:

System must:
1. Stop execution
2. Log issue
3. Surface missing data
4. Create corrective task if needed

Examples:
- Missing contact email
- No meeting notes
- No owner assigned

---

## Build Constraints

1. Workflow must be implemented in backend logic
2. Do not rely on AI to determine workflow steps
3. Always create:
   - WorkflowRun
   - ActivityEvent
4. No automatic stage transitions
5. No direct communication execution

---

## Definition of Success

The investor workflow is successful when:

1. Investors move through stages with full visibility
2. Follow-ups are consistent and tracked
3. Drafts are generated quickly and accurately
4. All outbound actions require approval
5. Full history is preserved for every deal