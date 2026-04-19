# Investor Agent Specification
- Strategic value
- Risks
- Recommended next step

### Draft Email
- Subject
- Body
- Suggested send timing
- Objective

## Approval Policy

The Investor Agent may create:
- draft communications
- draft tasks
- draft briefs
- approval requests

The Investor Agent may not:
- send an email
- schedule a meeting on calendar
- modify investment stage automatically
- bulk message contacts

All material outbound actions require human approval in Phase 1.

## Observability Requirements

Every investor-agent action must generate logs for:

1. Request type
2. Referenced entities
3. Output type
4. Whether draft records were created
5. Whether an approval was requested
6. Model used
7. Execution time

## Failure Handling

If required context is missing, the agent should:

1. State what is missing.
2. Fall back to structured summary if possible.
3. Avoid guessing.
4. Offer the next best internal action.

Example:
`No meeting notes were found for the last call. I can still draft a generic follow-up based on the last email and current stage, or create a task to log missing notes.`

## Build Sequence for Claude Code

### Step 1
Implement read-only investor summary service.

### Step 2
Implement investor ranking service.

### Step 3
Implement communication draft generation endpoint.

### Step 4
Implement task creation and approval request workflow.

### Step 5
Implement command handlers for investor use cases.

## Definition of Success

The Investor Agent is successful in Phase 1 when it can:

1. Accurately summarize the investor pipeline.
2. Prioritize investor opportunities using structured data.
3. Generate credible follow-up drafts.
4. Create follow-up tasks and approval-bound drafts.
5. Help the executive user move faster without losing control, accuracy, or traceability.