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
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/preflight_prepare.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/review/runtime/review_run.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-docio/runtime/actions_apply.py *)"
  - "Bash(rg *)"
  - "Bash(sed *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_stage.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_pack.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/runtime/diff_boundary_check.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_slice.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/review/runtime/review_report.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/review/runtime/review_pack.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/review/runtime/reviewer_tests.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/tasks_derive.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/progress_cli.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/stage_result.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/status_summary.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/tasklist_check.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/tasklist_check.py --fix *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_feature.py *)"
model: inherit
disable-model-invocation: true
user-invocable: true
---

Follow `feature-dev-aidd:aidd-core` and `feature-dev-aidd:aidd-loop`.

## Steps
1. Inputs: resolve active `<ticket>/<scope_key>` and verify loop/readmap artifacts required for review stage.
2. Preflight reference: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/preflight_prepare.py`. This step is mandatory and must produce `readmap/writemap`, actions template, and `stage.preflight.result.json`.
3. Read order after preflight: `readmap.md` -> loop pack -> review pack (if exists) -> rolling context pack; do not perform broad repo scan before these artifacts.
4. Run subagent `feature-dev-aidd:reviewer`.
5. Orchestration: produce review artifacts with `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review/runtime/review_report.py`, `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review/runtime/review_pack.py`, `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review/runtime/reviewer_tests.py`, and `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/tasks_derive.py`; then Fill actions.json for `aidd/reports/actions/<ticket>/<scope_key>/review.actions.json` and validate via `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review/runtime/review_run.py`.
6. Postflight reference: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-docio/runtime/actions_apply.py`. Apply actions via DocOps, then run boundary check, progress check, stage-result, status-summary.
7. Output: return review-stage contract, findings summary, and next action/handoff.

## Command contracts
### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review/runtime/review_run.py`
- When to run: as canonical review stage runtime before postflight.
- Inputs: ticket, scope/work-item context, and reviewer findings/actions payload.
- Outputs: validated review artifacts and stage status payload.
- Failure mode: non-zero exit on invalid review contracts or missing prerequisites.
- Next action: fix findings/actions inputs and rerun runtime validation.

### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/preflight_prepare.py`
- When to run: mandatory first step for review loop iterations.
- Inputs: `--ticket`, `--scope-key`, `--work-item-key`, `--stage review`, artifact target paths.
- Outputs: `readmap/writemap`, actions template, and preflight result artifact.
- Failure mode: boundary/precondition contract violation.
- Next action: correct preconditions or scope state, then rerun preflight.

### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-docio/runtime/actions_apply.py`
- When to run: mandatory final step after review actions are validated.
- Inputs: `--actions <path>` and optional `--apply-log <path>`.
- Outputs: applied actions plus progress/stage-result/status-summary artifacts.
- Failure mode: apply failure, boundary guard failure, or summary generation failure.
- Next action: inspect logs, fix blocking artifact/contract, rerun postflight.

## Notes
- Review stage runs targeted tests per policy.
- Use the existing rolling context pack; do not regenerate it in loop mode (DocOps updates only).

## Additional resources
- Contract schema: [CONTRACT.yaml](CONTRACT.yaml) (when: review artifacts or actions contract is ambiguous; why: verify required structure before rerunning runtime/postflight).
