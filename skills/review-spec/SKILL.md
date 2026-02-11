---
description: Review plan + PRD and gate readiness for implementation.
argument-hint: $1 [note...]
lang: ru
prompt_version: 1.0.19
source_version: 1.0.19
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(sed:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/progress.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/prd-check.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/prd-review.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh:*)"
model: inherit
disable-model-invocation: true
user-invocable: true
---

Follow `feature-dev-aidd:aidd-core`.

## Steps
1. Set active stage `review-plan`, then `review-prd`; keep active feature in sync.
2. Gate PRD readiness with `prd-check.sh`; block on failure.
3. Build the rolling context pack; run subagents in order: `plan-reviewer` then `prd-reviewer` (refresh between them).
4. Persist PRD review report with `prd-review.sh --report aidd/reports/prd/<ticket>.json`.
5. Return the output contract.

## Notes
- Planning stage: `AIDD:ACTIONS_LOG: n/a`.
