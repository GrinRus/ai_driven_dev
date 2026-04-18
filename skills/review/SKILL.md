---
name: review
description: Runs review-stage validation for scope changes, findings, and follow-up task derivation. Use when review stage needs verdict and handoff tasks. Do not use when the request is direct implementation execution in `implement` or QA validation in `qa`.
argument-hint: $1 [note...]
lang: en
prompt_version: 1.0.50
source_version: 1.0.50
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

Shared loop-stage contract: [../aidd-loop/stage-skill-contract.md](../aidd-loop/stage-skill-contract.md).

## Steps
1. Resolve active `<ticket>/<scope_key>` and read in order: `readmap.md` -> loop pack -> latest review pack when present -> rolling context pack.
2. Apply the shared loop-stage contract: canonical stage-chain only, internal preflight/postflight stay orchestration-only details, and manual write/create of `stage.review.result.json` is forbidden. `[AIDD_LOOP_POLICY:MANUAL_STAGE_RESULT_FORBIDDEN]`
3. Run subagent `feature-dev-aidd:reviewer` for the current bounded scope, produce review artifacts with `review_report.py`, `review_pack.py`, `reviewer_tests.py`, and `tasks_derive.py`, Fill actions.json at `aidd/reports/actions/<ticket>/<scope_key>/review.actions.json`, then validate it via `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review/runtime/review_run.py`.
4. Canonical stage-chain is `internal preflight -> stage runtime -> actions_apply.py/postflight -> python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/stage_result.py`; the only valid stage result path is `aidd/reports/loops/<ticket>/<scope_key>/stage.review.result.json`. `[AIDD_LOOP_POLICY:CANONICAL_STAGE_RESULT_PATH]`
5. Non-canonical stage-result paths under `skills/aidd-loop/runtime/` are forbidden. `[AIDD_LOOP_POLICY:NON_CANONICAL_STAGE_RESULT_FORBIDDEN]`
6. Do not run raw build/test commands from review orchestration. If stdout/stderr contains `can't open file .../skills/.../runtime/...`, stop with BLOCKED `runtime_path_missing_or_drift`.
7. Return one terminal payload with findings summary, evidence links, and the next canonical handoff.

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
- Shared loop-stage contract: [../aidd-loop/stage-skill-contract.md](../aidd-loop/stage-skill-contract.md) (when: shared stage-chain/read-order/fail-fast rules are needed; why: keep common loop-stage policy in one canonical file).
- Shared loop reference: [../aidd-loop/reference.md](../aidd-loop/reference.md) (when: shared stage-chain paths or loop invariants are unclear; why: reuse one canonical loop reference instead of duplicating command lore).
- Contract schema: [CONTRACT.yaml](CONTRACT.yaml) (when: review artifacts or actions contract is ambiguous; why: verify required structure before rerunning runtime/postflight).
