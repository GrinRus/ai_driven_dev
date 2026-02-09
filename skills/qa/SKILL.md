---
name: qa
description: Run QA checks and produce the QA report.
argument-hint: $1 [note...]
lang: ru
prompt_version: 1.0.31
source_version: 1.0.31
allowed-tools:
  - Read
  - Edit
  - Glob
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/qa/scripts/preflight.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/qa/scripts/run.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/qa/scripts/postflight.sh:*)"
  - "Bash(rg:*)"
  - "Bash(npm:*)"
  - "Bash(pnpm:*)"
  - "Bash(yarn:*)"
  - "Bash(pytest:*)"
  - "Bash(python:*)"
  - "Bash(go:*)"
  - "Bash(mvn:*)"
  - "Bash(make:*)"
  - "Bash(./gradlew:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/rlm-slice.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/set-active-stage.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/qa/scripts/qa.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/tasks-derive.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/progress.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/stage-result.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/status-summary.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/tasklist-check.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/tasklist-normalize.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/set-active-feature.sh:*)"
model: inherit
disable-model-invocation: true
user-invocable: true
context: fork
agent: qa
---

Follow `feature-dev-aidd:aidd-core` and `feature-dev-aidd:aidd-loop`.

## Steps
1. Preflight reference: `skills/qa/scripts/preflight.sh`. This step is mandatory and must produce `readmap/writemap`, actions template, and `stage.preflight.result.json`.
2. Read order after preflight: `readmap.md` -> loop pack -> review pack (if exists) -> rolling context pack; do not perform broad repo scan before these artifacts.
3. Run QA via `${CLAUDE_PLUGIN_ROOT}/skills/qa/scripts/qa.sh` and derive tasks if needed.
4. Fill actions.json (v1): create `aidd/reports/actions/<ticket>/<scope_key>/qa.actions.json` from template and validate schema via `skills/qa/scripts/run.sh` before postflight.
5. Postflight reference: `skills/qa/scripts/postflight.sh`. Apply actions via DocOps, then run progress check, stage-result, status-summary.

## Notes
- QA stage runs full tests per policy.
