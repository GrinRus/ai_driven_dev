---
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
2. Wrapper-only policy: use canonical slash stage command `/feature-dev-aidd:review <ticket>`; manual `preflight_prepare.py` invocation is forbidden for operators.
3. Manual write/create of `stage.review.result.json` is forbidden; stage-result files are produced only by wrapper postflight.
4. Read order after wrapper preflight artifacts: `readmap.md` -> loop pack -> review pack (if exists) -> rolling context pack; do not perform broad repo scan before these artifacts.
5. Run subagent `feature-dev-aidd:reviewer`.
6. Orchestration: produce review artifacts with `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review/runtime/review_report.py`, `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review/runtime/review_pack.py`, `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review/runtime/reviewer_tests.py`, and `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/tasks_derive.py`; then Fill actions.json for `aidd/reports/actions/<ticket>/<scope_key>/review.actions.json` and validate via `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review/runtime/review_run.py`.
7. Canonical stage wrapper chain is strict: `preflight -> review_run -> actions_apply.py/postflight -> stage_result.py`; it must produce `aidd/reports/loops/<ticket>/<scope_key>/stage.review.result.json`.
8. Output: return review-stage contract, findings summary, and next action/handoff.

## Command contracts
### `/feature-dev-aidd:review <ticket>`
- When to run: only operator entrypoint for review in seed/loop flow.
- Inputs: ticket + active scope/work-item context from loop artifacts.
- Outputs: wrapper-managed preflight/run/postflight artifacts and canonical stage result.
- Failure mode: deterministic BLOCKED/WARN when preconditions, boundaries, or contracts fail.
- Next action: inspect wrapper diagnostics/logs, fix inputs, rerun the same slash stage command.

### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review/runtime/review_run.py`
- When to run: as canonical review stage runtime before postflight.
- Inputs: ticket, scope/work-item context, and reviewer findings/actions payload.
- Outputs: validated review artifacts and stage status payload.
- Failure mode: non-zero exit on invalid review contracts or missing prerequisites.
- Next action: fix findings/actions inputs and rerun runtime validation.

### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-docio/runtime/actions_apply.py`
- When to run: mandatory final step in wrapper postflight after review actions are validated.
- Inputs: `--actions <path>` and optional `--apply-log <path>`.
- Outputs: applied actions plus progress/stage-result/status-summary artifacts.
- Failure mode: apply failure, boundary guard failure, or summary generation failure.
- Next action: inspect logs, fix blocking artifact/contract, rerun canonical slash-stage chain, and verify canonical stage result exists (`aidd/reports/loops/<ticket>/<scope_key>/stage.review.result.json`).

## Notes
- Review stage runs targeted tests per policy.
- Use the existing rolling context pack; do not regenerate it in loop mode (DocOps updates only).

## Additional resources
- Contract schema: [CONTRACT.yaml](CONTRACT.yaml) (when: review artifacts or actions contract is ambiguous; why: verify required structure before rerunning runtime/postflight).
