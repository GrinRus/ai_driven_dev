---
name: review
description: Runs review-stage validation for scope changes, findings, and follow-up task derivation. Use when review stage needs verdict and handoff tasks. Do not use when the request is direct implementation execution in `implement` or QA validation in `qa`.
argument-hint: $1 [note...]
lang: en
prompt_version: 1.0.48
source_version: 1.0.48
allowed-tools:
  - Read
  - Edit
  - Glob
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
1. Resolve active `<ticket>/<scope_key>` and verify loop/readmap artifacts required for review stage.
2. Stage-chain only: internal preflight/postflight stay internal; manual write/create of `stage.review.result.json` is forbidden. `[AIDD_LOOP_POLICY:MANUAL_STAGE_RESULT_FORBIDDEN]`
3. Runtime-path safety: use only commands declared below. If stdout/stderr shows `can't open file .../skills/.../runtime/...`, stop with BLOCKED `runtime_path_missing_or_drift`; do not guess alternate paths.
4. Test command safety: do not run raw build/test commands from review orchestration. Manage test requirement through `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review/runtime/reviewer_tests.py` and existing `aidd/reports/tests/**` evidence. If cwd/path resolution fails, record blocker `tests_cwd_mismatch`.
5. Read order after stage-chain preflight artifacts: `readmap.md` -> loop pack -> review pack (if exists) -> rolling context pack.
6. Run subagent `feature-dev-aidd:reviewer`.
7. Produce review artifacts with `review_report.py`, `review_pack.py`, `reviewer_tests.py`, and `tasks_derive.py`; then Fill actions.json at `aidd/reports/actions/<ticket>/<scope_key>/review.actions.json` as `aidd.actions.v1` and validate via `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review/runtime/review_run.py`.
8. Canonical stage-chain: internal preflight -> stage runtime -> actions_apply.py/postflight -> `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/stage_result.py`; expected output is `aidd/reports/loops/<ticket>/<scope_key>/stage.review.result.json`. `[AIDD_LOOP_POLICY:CANONICAL_STAGE_RESULT_PATH]`
9. Non-canonical stage-result path under `skills/aidd-loop/runtime/` is forbidden and counts as prompt-flow drift. `[AIDD_LOOP_POLICY:NON_CANONICAL_STAGE_RESULT_FORBIDDEN]`
10. Return one terminal review payload with findings summary and explicit next action or handoff.

## Command contracts
### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review/runtime/review_run.py`
- When to run: as canonical review stage runtime before postflight.
- Inputs: ticket, scope/work-item context, and reviewer findings/actions payload.
- Outputs: validated review artifacts and stage status payload.
- Failure mode: non-zero exit on invalid review contracts or missing prerequisites.
- Next action: fix findings/actions inputs and rerun runtime validation.

### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review/runtime/reviewer_tests.py`
- When to run: when reviewer must set/clear test requirement marker for the current scope.
- Inputs: `--ticket`, optional `--scope-key`, `--work-item-key`, and `--status` (`required|optional|skipped|not-required`).
- Outputs: reviewer marker at `aidd/reports/reviewer/<ticket>/<scope_key>.tests.json`.
- Failure mode: invalid status or unresolved ticket/scope context.
- Next action: fix marker arguments/context and rerun once; do not replace with ad-hoc shell test loops.

### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-docio/runtime/actions_apply.py`
- When to run: mandatory final step in stage-chain postflight after review actions are validated.
- Inputs: `--actions <path>` and optional `--apply-log <path>`.
- Outputs: applied actions plus progress/stage-result/status-summary artifacts.
- Failure mode: apply failure, boundary guard failure, or summary generation failure.
- Next action: inspect logs, fix blocking artifact/contract, rerun the stage-chain, and verify canonical stage result exists (`aidd/reports/loops/<ticket>/<scope_key>/stage.review.result.json`).

### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/stage_result.py`
- When to run: stage-chain postflight stage-result emission only (not operator/manual recovery command).
- Inputs: canonical postflight payload (`ticket`, `stage`, `result`, `scope-key`, `work-item-key`, evidence links).
- Outputs: canonical `aidd.stage_result.v1` at `aidd/reports/loops/<ticket>/<scope_key>/stage.review.result.json`.
- Failure mode: non-zero exit on missing required args or invalid stage-result contract fields.
- Next action: fix postflight payload generation and rerun the stage-chain; do not switch to non-canonical loop runtime paths.

## Additional resources
- Contract schema: [CONTRACT.yaml](CONTRACT.yaml) (when: review artifacts or actions contract is ambiguous; why: verify required structure before rerunning runtime/postflight).
