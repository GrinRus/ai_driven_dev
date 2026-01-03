---
description: "Final QA check"
argument-hint: "<TICKET> [note...]"
lang: en
prompt_version: 1.0.7
source_version: 1.0.7
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py:*)"
  - "Bash(claude-workflow qa:*)"
  - "Bash(claude-workflow progress:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_feature.py:*)"
model: inherit
disable-model-invocation: false
---

## Context
`/qa` runs the final check: runs sub-agent **qa** via `claude-workflow qa --gate`, updates tasklist QA section, and records progress. Runs after `/review`.

## Input Artifacts
- `@aidd/docs/prd/<ticket>.prd.md` (acceptance criteria).
- `@aidd/docs/plan/<ticket>.md`.
- `@aidd/docs/tasklist/<ticket>.md`.
- Test/gate logs.

## When to Run
- After `/review`, before release.
- Re-run after new changes.

## Automation & Hooks
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py qa` sets stage `qa`.
- The command must **invoke the sub-agent** **qa** (Claude: Run agent → qa) via `claude-workflow qa --gate`.
- `claude-workflow qa --ticket <ticket> --report "${CLAUDE_PLUGIN_ROOT:-./aidd}/reports/qa/<ticket>.json" --gate` writes the report.
- `claude-workflow progress --source qa --ticket <ticket>` records new `[x]`.

## What is Edited
- `aidd/docs/tasklist/<ticket>.md`.
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/reports/qa/<ticket>.json`.

## Step-by-step Plan
1. Set stage `qa`.
2. Run sub-agent **qa** via `claude-workflow qa --gate` and read the report.
3. Update QA section in tasklist with traceability to acceptance criteria.
4. Confirm progress via `claude-workflow progress`.

## Fail-fast & Questions
- Missing tasklist/PRD → stop and request updates.
- If the report is missing, rerun the CLI command and capture stderr.

## Expected Output
- Updated tasklist + QA report.
- Response includes `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## CLI Examples
- `/qa ABC-123`
