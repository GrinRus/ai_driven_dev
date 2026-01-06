---
description: "Combined plan + PRD review (review-plan + review-prd)"
argument-hint: "<TICKET> [note...]"
lang: en
prompt_version: 1.0.6
source_version: 1.0.6
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(claude-workflow progress:*)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT:-./aidd}/scripts/prd-review-agent.py:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_feature.py:*)"
model: inherit
disable-model-invocation: false
---

## Context
`/review-spec` bundles plan + PRD review and **runs the sub-agents** in order: `plan-reviewer` → `prd-reviewer`. It validates plan executability first, then reviews the PRD, updates `## Plan Review` and `## PRD Review`, and writes the report. Treat free-form notes after the ticket as review context.

## Input Artifacts
- `@aidd/docs/plan/<ticket>.md` — implementation plan.
- `@aidd/docs/prd/<ticket>.prd.md` — PRD and acceptance criteria.
- `@aidd/docs/research/<ticket>.md` — integration and reuse context.
- ADRs if present.

## When to Run
- After `/plan-new`, to complete review-plan and review-prd in one step.
- Re-run after major plan or PRD changes.

## Automation & Hooks
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py review-plan` sets stage `review-plan` before plan review.
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py review-prd` sets stage `review-prd` before PRD review.
- `gate-workflow` requires `Status: READY` in both `## Plan Review` and `## PRD Review` before code changes.
- `python3 "${CLAUDE_PLUGIN_ROOT:-./aidd}/scripts/prd-review-agent.py" --ticket <ticket> --report "${CLAUDE_PLUGIN_ROOT:-./aidd}/reports/prd/<ticket>.json" --emit-text` writes the PRD report.
- The command must **invoke the sub-agents** `plan-reviewer` and `prd-reviewer` (Claude: Run agent → …).

## What is Edited
- `aidd/docs/plan/<ticket>.md` — `## Plan Review` section.
- `aidd/docs/prd/<ticket>.prd.md` — `## PRD Review` section.
- `aidd/docs/tasklist/<ticket>.md` — move blocking action items (if any).
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/reports/prd/<ticket>.json` — PRD review report.

## Step-by-step Plan
1. Set stage `review-plan`, run sub-agent `plan-reviewer`, update `## Plan Review`.
2. If the plan is `BLOCKED`, stop and return questions.
3. Set stage `review-prd`, run sub-agent `prd-reviewer`, update `## PRD Review`.
4. Move blocking action items to tasklist and save the report via `prd-review-agent.py`.

## Fail-fast & Questions
- Missing plan/PRD/research → stop and request `/plan-new` or `/researcher`.
- If blocked, return `BLOCKED` and questions using `Question N (Blocker|Clarification)` with Why/Options/Default.

## Expected Output
- `## Plan Review` and `## PRD Review` updated with statuses.
- Report saved at `${CLAUDE_PLUGIN_ROOT:-./aidd}/reports/prd/<ticket>.json`.
- Response includes `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## CLI Examples
- `/review-spec ABC-123`
