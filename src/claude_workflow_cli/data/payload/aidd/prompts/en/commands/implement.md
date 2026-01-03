---
description: "Implement feature by plan + selective tests"
argument-hint: "<TICKET> [note...]"
lang: en
prompt_version: 1.1.9
source_version: 1.1.9
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/hooks/format-and-test.sh:*)"
  - "Bash(claude-workflow progress:*)"
  - "Bash(git:*)"
model: inherit
disable-model-invocation: false
---

## Context
`/implement` invokes **implementer** to execute the next iteration from the plan/tasklist. Free-form notes after the ticket are iteration context.

## Input Artifacts
- `@aidd/docs/plan/<ticket>.md`.
- `@aidd/docs/tasklist/<ticket>.md`.
- `@aidd/docs/prd/<ticket>.prd.md`, `@aidd/docs/research/<ticket>.md` as needed.

## When to Run
- After `/tasks-new`, when plan/reviews are ready.
- Repeat per iteration.

## Automation & Hooks
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py implement` sets stage `implement`.
- The command must **invoke the sub-agent** **implementer** (Claude: Run agent → implementer).
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/hooks/format-and-test.sh` runs on Stop/SubagentStop.
- `claude-workflow progress --source implement --ticket <ticket>` confirms new `- [x]`.

## What is Edited
- Code/config + `aidd/docs/tasklist/<ticket>.md`.

## Step-by-step Plan
1. Set stage `implement`.
2. Run sub-agent **implementer** with the iteration context.
3. Ensure tasklist is updated and progress confirmed.

## Fail-fast & Questions
- Missing plan/tasklist or reviews — stop and request prerequisites.
- Failing tests/blockers → stop before continuing.

## Expected Output
- Updated code + tasklist.
- Response includes `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## CLI Examples
- `/implement ABC-123`
