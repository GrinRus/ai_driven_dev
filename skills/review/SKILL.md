---
name: review
description: Review changes, produce feedback, and derive tasks.
argument-hint: $1 [note...]
lang: ru
prompt_version: 1.0.35
source_version: 1.0.35
allowed-tools:
  - Read
  - Edit
  - Glob
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/review/scripts/preflight.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/review/scripts/run.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/review/scripts/postflight.sh:*)"
  - "Bash(rg:*)"
  - "Bash(sed:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/loop-pack.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/diff-boundary-check.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/rlm-slice.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/review/scripts/review-report.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/review/scripts/review-pack.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/review/scripts/reviewer-tests.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/progress.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/stage-result.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/status-summary.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/tasklist-normalize.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh:*)"
model: inherit
disable-model-invocation: true
user-invocable: true
context: fork
agent: reviewer
---

Follow `feature-dev-aidd:aidd-core` and `feature-dev-aidd:aidd-loop`.

## Steps
1. Preflight reference: `skills/review/scripts/preflight.sh`. This step is mandatory and must produce `readmap/writemap`, actions template, and `stage.preflight.result.json`.
2. Read order after preflight: `readmap.md` -> loop pack -> review pack (if exists) -> rolling context pack; do not perform broad repo scan before these artifacts.
3. Run subagent `feature-dev-aidd:reviewer` (fork).
4. Produce review artifacts with `review-report.sh`, `review-pack.sh`, `reviewer-tests.sh`, and `tasks-derive.sh` as applicable.
5. Fill actions.json (v1): create `aidd/reports/actions/<ticket>/<scope_key>/review.actions.json` from template and validate schema via `skills/review/scripts/run.sh` before postflight.
6. Postflight reference: `skills/review/scripts/postflight.sh`. Apply actions via DocOps, then run boundary check, progress check, stage-result, status-summary.

## Notes
- Review stage runs targeted tests per policy.
- Use the existing rolling context pack; do not regenerate it in loop mode (DocOps updates only).
- Legacy shim only: `context-pack.sh` exists for compatibility; do not use it in loop stage.
