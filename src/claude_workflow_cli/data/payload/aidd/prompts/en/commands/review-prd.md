---
description: "Review PRD readiness"
argument-hint: "<TICKET> [note...]"
lang: en
prompt_version: 1.0.4
source_version: 1.0.4
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(claude-workflow progress:*)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT:-./aidd}/scripts/prd-review-agent.py:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py:*)"
model: inherit
disable-model-invocation: false
---

## Context
`/review-prd` runs after `/review-plan` and before `/tasks-new`. It sets stage `review-prd`, calls `prd-reviewer`, updates `## PRD Review`, and stores the report at `${CLAUDE_PLUGIN_ROOT:-./aidd}/reports/prd/<ticket>.json`. Free-form notes after the ticket are review context.

## Input Artifacts
- `@aidd/docs/prd/<ticket>.prd.md`.
- `@aidd/docs/plan/<ticket>.md` with `## Plan Review` READY.
- `@aidd/docs/research/<ticket>.md`.
- ADRs (if any).

## When to Run
- After `/review-plan`, before `/tasks-new`.
- Re-run after substantial PRD changes.

## Automation & Hooks
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py review-prd` sets stage `review-prd`.
- `gate-workflow` requires `## PRD Review` to be READY before code changes.
- `python3 "${CLAUDE_PLUGIN_ROOT:-./aidd}/scripts/prd-review-agent.py" --ticket <ticket> --report "${CLAUDE_PLUGIN_ROOT:-./aidd}/reports/prd/<ticket>.json" --emit-text` writes the report.

## What is Edited
- `aidd/docs/prd/<ticket>.prd.md` — `## PRD Review`.
- `aidd/docs/tasklist/<ticket>.md` — blocking action items.
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/reports/prd/<ticket>.json`.

## Step-by-step Plan
1. Set stage `review-prd`.
2. Verify `## Plan Review` is READY.
3. Invoke `prd-reviewer` and update `## PRD Review`.
4. Move blocking action items into tasklist.
5. Write the JSON report.

## Fail-fast & Questions
- Missing PRD or plan/plan review → stop and request prerequisites.
- Use the required question format for blockers.

## Expected Output
- Updated `## PRD Review` with status/findings/action items.
- Report saved to `${CLAUDE_PLUGIN_ROOT:-./aidd}/reports/prd/<ticket>.json`.
- Blocking action items moved to tasklist.

## CLI Examples
- `/review-prd ABC-123`
