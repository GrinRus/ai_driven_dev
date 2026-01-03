---
description: "Code review and feedback into tasklist"
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
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py:*)"
  - "Bash(claude-workflow reviewer-tests:*)"
  - "Bash(claude-workflow progress:*)"
model: inherit
disable-model-invocation: false
---

## Context
`/review` invokes **reviewer** to audit changes before QA and records findings in the tasklist. Free-form notes after the ticket are review context.

## Input Artifacts
- Diff/PR.
- `@aidd/docs/prd/<ticket>.prd.md`, `@aidd/docs/plan/<ticket>.md`, `@aidd/docs/tasklist/<ticket>.md`.
- Test/gate logs and `reports/reviewer/<ticket>.json` if present.

## When to Run
- After `/implement`, before `/qa`.
- Repeat until blockers are resolved.

## Automation & Hooks
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py review` sets stage `review`.
- The command must **invoke the sub-agent** **reviewer** (Claude: Run agent → reviewer).
- `claude-workflow reviewer-tests --status required|optional|clear` toggles test requirement.
- `claude-workflow progress --source review --ticket <ticket>` records new `[x]`.

## What is Edited
- `aidd/docs/tasklist/<ticket>.md`.

## Step-by-step Plan
1. Set stage `review`.
2. Run sub-agent **reviewer** and update the tasklist.
3. Request tests if needed via `reviewer-tests`.
4. Confirm progress via `claude-workflow progress`.

## Fail-fast & Questions
- Missing tasklist/plan → stop and request updates.
- If diff deviates from the ticket scope → stop and align.

## Expected Output
- Updated tasklist.
- Response includes `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## CLI Examples
- `/review ABC-123`
