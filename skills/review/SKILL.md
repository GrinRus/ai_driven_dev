---
name: review
description: Review changes, produce feedback, and derive tasks.
argument-hint: $1 [note...]
lang: ru
prompt_version: 1.0.33
source_version: 1.0.33
allowed-tools:
  - Read
  - Edit
  - Glob
  - "Bash(rg:*)"
  - "Bash(sed:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/loop-pack.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/diff-boundary-check.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/review-report.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/review-pack.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/reviewer-tests.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/progress.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/context-pack.sh:*)"
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
1. Preflight reference: `skills/review/scripts/preflight.sh`. Ensure active feature/stage and loop pack readiness.
2. Run subagent `feature-dev-aidd:reviewer` (fork). First action: loop pack -> review pack (if any) -> rolling context pack.
3. Produce review artifacts with `review-report.sh`, `review-pack.sh`, `reviewer-tests.sh`, and `tasks-derive.sh` as applicable.
4. Fill actions.json: create `aidd/reports/actions/<ticket>/<scope_key>/review.actions.json` from template and validate schema before postflight.
5. Postflight reference: `skills/review/scripts/postflight.sh`. Run boundary check, progress check, stage-result, status-summary.

## Notes
- Review stage runs targeted tests per policy.
