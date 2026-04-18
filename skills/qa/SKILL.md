---
name: qa
description: Runs QA-stage validation, report generation, and postflight actions for the current scope. Use when QA stage is ready for loop verification. Do not use when the request belongs to `review` findings synthesis or `implement` execution loops.
argument-hint: $1 [note...]
lang: en
prompt_version: 1.0.43
source_version: 1.0.43
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

## Steps
1. Resolve active `<ticket>/<scope_key>` and read in order: `readmap.md` -> loop pack -> latest review pack when present -> rolling context pack.
2. Execute only via canonical stage-chain orchestration. Internal preflight and postflight are orchestration details, not operator commands.
3. Manual write/create of `stage.qa.result.json` is forbidden. `[AIDD_LOOP_POLICY:MANUAL_STAGE_RESULT_FORBIDDEN]`
4. Run subagent `feature-dev-aidd:qa` for the current bounded scope only.
5. Fill actions.json: run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/qa/runtime/qa.py`, derive follow-up tasks if needed, then validate `aidd/reports/actions/<ticket>/<scope_key>/qa.actions.json` via `python3 ${CLAUDE_PLUGIN_ROOT}/skills/qa/runtime/qa_run.py`.
6. Canonical stage-chain: internal preflight -> stage runtime -> actions_apply.py/postflight -> `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/stage_result.py`; the only valid stage result path is `aidd/reports/loops/<ticket>/<scope_key>/stage.qa.result.json`. `[AIDD_LOOP_POLICY:CANONICAL_STAGE_RESULT_PATH]`
7. Non-canonical stage-result path under `skills/aidd-loop/runtime/` is forbidden. `[AIDD_LOOP_POLICY:NON_CANONICAL_STAGE_RESULT_FORBIDDEN]`
8. If preflight context is missing, stop with canonical handoff `/feature-dev-aidd:implement <ticket>`. If actions payload is invalid, stop with canonical handoff `/feature-dev-aidd:tasks-new <ticket>`.
9. If stdout/stderr contains `can't open file .../skills/.../runtime/...`, stop with BLOCKED `runtime_path_missing_or_drift`. Do not invent manual recovery loops or ad-hoc test commands from arbitrary cwd.
10. Return one terminal QA payload with report paths and the next canonical action.

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
- Contract schema: [CONTRACT.yaml](CONTRACT.yaml) (when: QA action/report requirements are unclear; why: verify mandatory fields before runtime validation and postflight).
