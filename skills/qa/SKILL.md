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
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/preflight_prepare.py *)"
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
  - "Bash(./gradlew *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_slice.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_stage.py *)"
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
1. Inputs: resolve active `<ticket>/<scope_key>` and validate QA prerequisites from loop/readmap artifacts.
2. Preflight reference: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/preflight_prepare.py`. This step is mandatory and must produce `readmap/writemap`, actions template, and `stage.preflight.result.json`.
3. Read order after preflight: `readmap.md` -> loop pack -> review pack (if exists) -> rolling context pack; do not perform broad repo scan before these artifacts.
4. Run subagent `feature-dev-aidd:qa`.
5. Orchestration: run QA via `python3 ${CLAUDE_PLUGIN_ROOT}/skills/qa/runtime/qa.py`, derive tasks if needed, then Fill actions.json for `aidd/reports/actions/<ticket>/<scope_key>/qa.actions.json` and validate via `python3 ${CLAUDE_PLUGIN_ROOT}/skills/qa/runtime/qa_run.py`.
6. Postflight reference: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-docio/runtime/actions_apply.py`. Apply actions via DocOps, then run progress check, stage-result, status-summary.
7. Output: return QA status contract with report paths and explicit next action.

## Command contracts
### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/qa/runtime/qa_run.py`
- When to run: as canonical QA stage runtime before postflight.
- Inputs: ticket, scope/work-item context, QA findings, and actions payload.
- Outputs: validated QA report artifacts and stage status payload.
- Failure mode: non-zero exit when report/actions schema or required stage inputs are invalid.
- Next action: fix QA findings/actions contract issues and rerun runtime validation.

### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/preflight_prepare.py`
- When to run: mandatory first step for QA loop iterations.
- Inputs: `--ticket`, `--scope-key`, `--work-item-key`, `--stage qa`, artifact target paths.
- Outputs: `readmap/writemap`, actions template, and preflight result artifact.
- Failure mode: missing artifacts or boundary/precondition validation failure.
- Next action: repair prerequisites and rerun preflight.

### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-docio/runtime/actions_apply.py`
- When to run: mandatory final step after QA actions are validated.
- Inputs: `--actions <path>` and optional `--apply-log <path>`.
- Outputs: applied actions plus progress/stage-result/status-summary artifacts.
- Failure mode: apply failure, progress update failure, or status summary failure.
- Next action: inspect logs, fix blocking contract issues, rerun postflight.

## Notes
- QA stage runs full tests per policy.

## Additional resources
- Contract schema: [CONTRACT.yaml](CONTRACT.yaml) (when: QA action/report requirements are unclear; why: verify mandatory fields before runtime validation and postflight).
