---
description: Run QA checks and produce the QA report.
argument-hint: $1 [note...]
lang: ru
prompt_version: 1.0.33
source_version: 1.0.33
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
  - "Bash(./gradlew *)"
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
1. Inputs: resolve active `<ticket>/<scope_key>` and validate QA prerequisites from loop/readmap artifacts.
2. Wrapper-only policy: execute only via wrapper chain; manual `preflight_prepare.py` invocation is forbidden for operators.
3. Manual write/create of `stage.qa.result.json` is forbidden; stage-result files are produced only by wrapper postflight.
4. Read order after wrapper preflight artifacts: `readmap.md` -> loop pack -> review pack (if exists) -> rolling context pack; do not perform broad repo scan before these artifacts.
5. Run subagent `feature-dev-aidd:qa`.
6. Orchestration: run QA via `python3 skills/qa/runtime/qa.py`, derive tasks if needed, then Fill actions.json for `aidd/reports/actions/<ticket>/<scope_key>/qa.actions.json` and validate via `python3 skills/qa/runtime/qa_run.py`.
7. Canonical stage wrapper chain is strict: `preflight -> qa_run -> actions_apply.py/postflight -> stage_result.py`.
8. Output: return QA status contract with report paths and explicit canonical next action (`/feature-dev-aidd:status <ticket>` or `/feature-dev-aidd:tasks-new <ticket>` when follow-up tasks are required).

## Command contracts
### `python3 skills/qa/runtime/qa_run.py`
- When to run: as canonical QA stage runtime before postflight.
- Inputs: ticket, scope/work-item context, QA findings, and actions payload.
- Outputs: validated QA report artifacts and stage status payload.
- Failure mode: non-zero exit when report/actions schema or required stage inputs are invalid.
- Next action: fix QA findings/actions contract issues and rerun runtime validation.

### `python3 skills/aidd-docio/runtime/actions_apply.py`
- When to run: mandatory final step in wrapper postflight after QA actions are validated.
- Inputs: `--actions <path>` and optional `--apply-log <path>`.
- Outputs: applied actions plus progress/stage-result/status-summary artifacts.
- Failure mode: apply failure, progress update failure, or status summary failure.
- Next action: inspect logs, fix blocking contract issues, rerun the wrapper chain.

## Notes
- QA stage runs full tests per policy.

## Additional resources
- Contract schema: [CONTRACT.yaml](CONTRACT.yaml) (when: QA action/report requirements are unclear; why: verify mandatory fields before runtime validation and postflight).
