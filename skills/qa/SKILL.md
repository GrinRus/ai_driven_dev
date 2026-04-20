---
name: qa
description: Runs QA-stage validation, report generation, and postflight actions for the current scope. Use when QA stage is ready for loop verification. Do not use when the request belongs to `review` findings synthesis or `implement` execution loops.
argument-hint: $1 [note...]
lang: en
prompt_version: 1.0.45
source_version: 1.0.45
allowed-tools:
  - Read
  - Edit
  - Glob
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/qa/runtime/qa_run.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/qa/runtime/qa.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-docio/runtime/actions_apply.py *)"
  - "Bash(rg *)"
  - "Bash(npm *)"
  - "Bash(pnpm *)"
  - "Bash(yarn *)"
  - "Bash(pytest *)"
  - "Bash(python *)"
  - "Bash(go *)"
  - "Bash(mvn *)"
  - "Bash(make *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_slice.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_stage.py *)"
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
1. Resolve active `<ticket>/<scope_key>`, validate QA prerequisites from loop/readmap artifacts, and read in order: `readmap.md` -> loop pack -> latest review pack when present -> rolling context pack. Do not broad-scan the repo before these artifacts.
2. Apply the shared loop-stage contract: canonical stage-chain only, internal preflight/postflight stay orchestration-only details, and manual write/create of `stage.qa.result.json` is forbidden. `[AIDD_LOOP_POLICY:MANUAL_STAGE_RESULT_FORBIDDEN]`
3. Retry safety: do not rerun the same failing shell command more than once without new evidence/artifacts. For cwd/build mismatches, stop with blocker and handoff instead of looped retries.
4. Fail fast when stage-chain context is missing or invalid: if preflight/stage-chain context is missing (`reason_code=preflight_missing`) or workflow paths resolve to non-workspace targets, stop immediately with terminal BLOCKED for the current run and explicit next action `/feature-dev-aidd:implement <ticket>`.
5. Actions contract hardening: if `actions-apply` reports schema/payload mismatch (`reason_code=contract_mismatch_actions_shape`) or the actions payload is otherwise invalid, do not attempt guessed retries or manual payload edits; return terminal BLOCKED with canonical handoff `/feature-dev-aidd:tasks-new <ticket>`.
6. Run subagent `feature-dev-aidd:qa` for the current bounded scope, run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/qa/runtime/qa.py`, derive follow-up tasks when needed, then Fill actions.json at `aidd/reports/actions/<ticket>/<scope_key>/qa.actions.json` strictly as `aidd.actions.v1` (`schema_version`, `allowed_action_types`, canonical `type` + `params`) with action types only from `{tasklist_ops.set_iteration_done, tasklist_ops.append_progress_log, tasklist_ops.next3_recompute, context_pack_ops.context_pack_update}`, and validate it via `python3 ${CLAUDE_PLUGIN_ROOT}/skills/qa/runtime/qa_run.py`. Do not use raw ad-hoc test commands from arbitrary cwd as a recovery path.
7. Canonical stage-chain is `internal preflight -> stage runtime -> actions_apply.py/postflight -> python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/stage_result.py`; the only valid stage result path is `aidd/reports/loops/<ticket>/<scope_key>/stage.qa.result.json`. `[AIDD_LOOP_POLICY:CANONICAL_STAGE_RESULT_PATH]`
8. Non-canonical stage-result paths under `skills/aidd-loop/runtime/` are forbidden. `[AIDD_LOOP_POLICY:NON_CANONICAL_STAGE_RESULT_FORBIDDEN]`
9. If stdout/stderr contains `can't open file .../skills/.../runtime/...`, stop with immediate BLOCKED `runtime_path_missing_or_drift`; one runtime-path error is terminal for the current run, and you must not invent manual recovery loops or ad-hoc test commands from arbitrary cwd.
10. Return one terminal QA payload with report paths and explicit canonical next action (`/feature-dev-aidd:status <ticket>` or `/feature-dev-aidd:tasks-new <ticket>` when follow-up tasks are required). Ensure one terminal payload per run with no repeated guessed recovery loops.

## Command contracts
### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/qa/runtime/qa_run.py`
- When to run: as canonical QA stage runtime before postflight.
- Inputs: ticket, scope/work-item context, QA findings, and actions payload.
- Outputs: validated QA report artifacts and stage status payload.
- Failure mode: non-zero exit when report/actions schema or required stage inputs are invalid.
- Next action: fix QA findings/actions contract issues and rerun runtime validation.

### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-docio/runtime/actions_apply.py`
- When to run: mandatory final step in stage-chain postflight after QA actions are validated.
- Inputs: `--actions <path>` and optional `--apply-log <path>`.
- Outputs: applied actions plus progress/stage-result/status-summary artifacts.
- Failure mode: apply failure, progress update failure, or status summary failure.
- Next action: inspect logs, fix blocking contract issues, rerun the stage-chain.

### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/stage_result.py`
- When to run: stage-chain postflight stage-result emission only (not operator/manual recovery command).
- Inputs: canonical postflight payload (`ticket`, `stage`, `result`, `scope-key`, `work-item-key`, evidence links).
- Outputs: canonical `aidd.stage_result.v1` at `aidd/reports/loops/<ticket>/<scope_key>/stage.qa.result.json`.
- Failure mode: non-zero exit on missing required args or invalid stage-result contract fields.
- Next action: fix postflight payload generation and rerun the stage-chain; do not switch to non-canonical loop runtime paths.

## Notes
- QA stage runs full tests per policy.

## Additional resources
- Shared loop-stage contract: [../aidd-loop/stage-skill-contract.md](../aidd-loop/stage-skill-contract.md) (when: shared stage-chain/read-order/fail-fast rules are needed; why: keep common loop-stage policy in one canonical file).
- Shared loop reference: [../aidd-loop/reference.md](../aidd-loop/reference.md) (when: shared stage-chain paths or loop invariants are unclear; why: reuse one canonical loop reference instead of duplicating command lore).
- Contract schema: [CONTRACT.yaml](CONTRACT.yaml) (when: QA action/report requirements are unclear; why: verify mandatory fields before runtime validation and postflight).
