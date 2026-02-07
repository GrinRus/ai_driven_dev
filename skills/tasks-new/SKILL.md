---
name: tasks-new
description: Create or refine tasklist based on plan/PRD/spec.
argument-hint: $1 [note...]
lang: ru
prompt_version: 1.1.19
source_version: 1.1.19
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(sed:*)"
  - "Bash(cat:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/prd-check.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh:*)"
model: inherit
disable-model-invocation: true
user-invocable: true
context: fork
agent: tasklist-refiner
---

Follow `feature-dev-aidd:aidd-core`.

## Steps
1. Set active stage `tasklist` and active feature.
2. Gate PRD readiness with `prd-check.sh`.
3. Build the rolling context pack.
4. Run subagent `feature-dev-aidd:tasklist-refiner` (fork). First action: read the rolling context pack.
5. Validate via `tasklist-check.sh`; update `aidd/docs/tasklist/<ticket>.md`.
6. Return the output contract and next step `/feature-dev-aidd:implement <ticket>`.

## Notes
- Planning stage: `AIDD:ACTIONS_LOG: n/a`.
