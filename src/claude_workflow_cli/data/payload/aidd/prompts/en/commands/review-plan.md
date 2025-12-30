---
description: "Review implementation plan before PRD review"
argument-hint: "<TICKET> [note...]"
lang: en
prompt_version: 1.0.1
source_version: 1.0.1
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py:*)"
model: inherit
disable-model-invocation: false
---

## Context
`/review-plan` reviews the implementation plan after `/plan-new` and before `/review-prd`. It sets the `review-plan` stage, invokes `plan-reviewer`, and updates `## Plan Review` in `aidd/docs/plan/<ticket>.md`. Free-form notes after the ticket should be treated as review context.

## Input Artifacts
- `@aidd/docs/plan/<ticket>.md` — implementation plan.
- `@aidd/docs/prd/<ticket>.prd.md` — goals and acceptance criteria.
- `@aidd/docs/research/<ticket>.md` — integration/reuse context.
- ADRs (if any).

## When to Run
- After `/plan-new`, before `/review-prd` and `/tasks-new`.
- Re-run after substantial plan updates.

## Automation & Hooks
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py review-plan` sets stage `review-plan`.
- `gate-workflow` blocks `review-prd`/`tasks-new` until `Status: READY` is set in `## Plan Review`.

## What is Edited
- `aidd/docs/plan/<ticket>.md` — section `## Plan Review`.

## Step-by-step Plan
1. Set stage `review-plan`: `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py review-plan`.
2. Ensure the plan exists and has a current status (READY/PENDING/BLOCKED).
3. Invoke sub-agent **plan-reviewer** with PRD/research/ADR context.
4. Update `## Plan Review` and return status.

## Fail-fast & Questions
- Missing plan or PRD/research → stop and request `/plan-new` or `/researcher`.
- If blockers exist, return `BLOCKED` and ask questions in the required format (`Question N (Blocker|Clarification)` + Why/Options/Default).

## Expected Output
- `aidd/docs/plan/<ticket>.md` updated with `## Plan Review` and status.
- Response includes `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## CLI Examples
- `/review-plan ABC-123`
