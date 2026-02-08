---
name: plan-new
description: Draft the implementation plan from PRD and research.
argument-hint: $1 [note...]
lang: ru
prompt_version: 1.1.12
source_version: 1.1.12
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(sed:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/prd-check.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/plan-new/scripts/research-check.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/rlm-slice.sh:*)"
model: inherit
disable-model-invocation: true
user-invocable: true
---

Follow `feature-dev-aidd:aidd-core`.

## Steps
1. Set active stage `plan` and active feature.
2. Gate readiness with `prd-check.sh` and `research-check.sh`; block if either fails.
3. Build the rolling context pack.
4. Run subagents in order: `feature-dev-aidd:planner` then `feature-dev-aidd:validator`. Refresh the pack between them.
5. Update `aidd/docs/plan/<ticket>.md` and return the output contract.

## Notes
- Planning stage: `AIDD:ACTIONS_LOG: n/a`.
