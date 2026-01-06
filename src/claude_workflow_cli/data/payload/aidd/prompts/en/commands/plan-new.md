---
description: "Implementation plan + validation"
argument-hint: "<TICKET> [note...]"
lang: en
prompt_version: 1.1.0
source_version: 1.1.0
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_feature.py:*)"
  - "Bash(claude-workflow research-check:*)"
model: inherit
disable-model-invocation: false
---

## Context
`/plan-new` builds the implementation plan from PRD + research, sets stage `plan`, and runs sub-agents `planner` then `validator`. The next step is `/review-spec`. Free-form notes after the ticket should be folded into the plan.

## Input Artifacts
- `@aidd/docs/prd/<ticket>.prd.md` — must be `Status: READY`.
- `@aidd/docs/research/<ticket>.md` — validated via `claude-workflow research-check`.
- ADRs (if any).

## When to Run
- After `/idea-new` and `/researcher` (if needed).
- Re-run when requirements change materially.

## Automation & Hooks
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py plan` sets stage `plan`.
- The command must **invoke the sub-agents** `planner` and `validator` (Claude: Run agent → planner/validator); `BLOCKED` returns questions.
- Run `claude-workflow research-check --ticket <ticket>` before planner.
- `gate-workflow` requires a plan before code changes.

## What is Edited
- `aidd/docs/plan/<ticket>.md`.
- Sync open questions/risks with PRD if needed.

## Step-by-step Plan
1. Set stage `plan`.
2. Verify PRD is READY, then run `claude-workflow research-check --ticket <ticket>` and stop on failure.
3. Run sub-agent `planner` to create/update the plan.
4. Run sub-agent `validator`; if `BLOCKED`, return questions.
5. Ensure required sections exist (files/modules, iterations, tests, risks).

## Fail-fast & Questions
- Missing READY PRD or failed `research-check` — stop and request prerequisites.
- If validator returns `BLOCKED`, ask questions in the required format.

## Expected Output
- Updated and validated `aidd/docs/plan/<ticket>.md`.
- Response includes `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions` (next step: `/review-spec`).

## CLI Examples
- `/plan-new ABC-123`
