---
description: "Generate the tasklist (`aidd/docs/tasklist/<ticket>.md`)"
argument-hint: "<TICKET> [note...]"
lang: en
prompt_version: 1.0.5
source_version: 1.0.5
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
`/tasks-new` creates or rebuilds `aidd/docs/tasklist/<ticket>.md` from the plan/PRD/reviews. Tasklist drives `/implement`, `/review`, `/qa`. Free-form notes after the ticket should be included as a tasklist note.

## Input Artifacts
- `@aidd/docs/plan/<ticket>.md`.
- `@aidd/docs/prd/<ticket>.prd.md` + `## PRD Review`.
- `@aidd/docs/research/<ticket>.md`.
- Template `@templates/tasklist.md` if creating from scratch.

## When to Run
- After `/review-spec`, before `/implement`.
- Re-run after plan/PRD changes.

## Automation & Hooks
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py tasklist` sets stage `tasklist`.
- `gate-workflow` checks tasklist presence and new `- [x]`.

## What is Edited
- `aidd/docs/tasklist/<ticket>.md` — front matter + `Next 3` + `Handoff inbox`.

## Step-by-step Plan
1. Set stage `tasklist`.
2. Create/open the tasklist; if missing, copy `templates/tasklist.md`.
3. Update front matter (Ticket/Slug/Status/PRD/Plan/Research/Updated).
4. Map plan iterations and PRD Review action items into checklists.
5. Fill `Next 3` and `Handoff inbox`.

## Fail-fast & Questions
- Missing plan/Plan Review/PRD Review READY — stop and request `/review-spec`.
- If owners are unclear, ask for clarification.

## Expected Output
- Updated `aidd/docs/tasklist/<ticket>.md` with `Next 3` and `Handoff inbox`.
- Response includes `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## CLI Examples
- `/tasks-new ABC-123`
