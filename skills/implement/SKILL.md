---
description: Implement the next work item with loop discipline.
argument-hint: $1 [note...] [test=fast|targeted|full|none] [tests=<filters>] [tasks=<task1,task2>]
lang: ru
prompt_version: 1.1.40
source_version: 1.1.40
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/preflight_prepare.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/implement/runtime/implement_run.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-docio/runtime/actions_apply.py *)"
  - "Bash(rg *)"
  - "Bash(sed *)"
  - "Bash(cat *)"
  - "Bash(xargs *)"
  - "Bash(npm *)"
  - "Bash(pnpm *)"
  - "Bash(yarn *)"
  - "Bash(pytest *)"
  - "Bash(python *)"
  - "Bash(go *)"
  - "Bash(mvn *)"
  - "Bash(make *)"
  - "Bash(./gradlew *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_stage.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/prd_check.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_pack.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/runtime/diff_boundary_check.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_slice.py *)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/hooks/format-and-test.sh *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/progress_cli.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/stage_result.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/status_summary.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/tasklist_check.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/tasklist_check.py --fix *)"
  - "Bash(git status *)"
  - "Bash(git diff *)"
  - "Bash(git log *)"
  - "Bash(git show *)"
  - "Bash(git rev-parse *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_feature.py *)"
model: inherit
disable-model-invocation: true
user-invocable: true
---

Follow `feature-dev-aidd:aidd-core` and `feature-dev-aidd:aidd-loop`.

## Steps
1. Inputs: resolve active `<ticket>/<scope_key>` and confirm loop artifacts are present for implement stage.
2. Wrapper-only policy: use canonical slash stage command `/feature-dev-aidd:implement <ticket>`; manual `preflight_prepare.py` invocation is forbidden for operators.
3. Manual write/create of `stage.implement.result.json` is forbidden; stage-result files are produced only by wrapper postflight.
4. Read order after wrapper preflight artifacts: `readmap.md` -> loop pack -> review pack (if exists) -> rolling context pack; do not perform broad repo scan before these artifacts.
5. Run subagent `feature-dev-aidd:implementer`.
6. Orchestration: use the existing rolling context pack (do not regenerate it), Fill actions.json (v1) at `aidd/reports/actions/<ticket>/<scope_key>/implement.actions.json`, and validate schema via `python3 ${CLAUDE_PLUGIN_ROOT}/skills/implement/runtime/implement_run.py`.
7. Canonical stage wrapper chain is strict: `preflight -> implement_run -> actions_apply.py/postflight -> stage_result.py`; it must produce `aidd/reports/loops/<ticket>/<scope_key>/stage.implement.result.json`.
8. Output: return stage contract + updated artifacts with explicit handoff/next action.

## Command contracts
### `/feature-dev-aidd:implement <ticket>`
- When to run: only operator entrypoint for implement in seed/loop flow.
- Inputs: ticket + active scope/work-item context from loop artifacts.
- Outputs: wrapper-managed preflight/run/postflight artifacts and canonical stage result.
- Failure mode: deterministic BLOCKED/WARN when preconditions, boundaries, or contracts fail.
- Next action: inspect wrapper diagnostics/logs, fix inputs, rerun the same slash stage command.

### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/implement/runtime/implement_run.py`
- When to run: as canonical implement stage runtime before postflight.
- Inputs: ticket, scope/work-item context, and validated actions payload.
- Outputs: stage validation artifacts and status payload for downstream postflight.
- Failure mode: non-zero exit for invalid actions schema or missing stage prerequisites.
- Next action: fix actions/preconditions and rerun runtime validation before postflight.

### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-docio/runtime/actions_apply.py`
- When to run: mandatory final step in wrapper postflight after actions validation.
- Inputs: `--actions <path>` and optional `--apply-log <path>`.
- Outputs: applied actions, progress/status artifacts, and apply logs.
- Failure mode: DocOps apply failure, boundary guard failure, or status-summary failure.
- Next action: inspect action/apply logs, fix root cause, rerun canonical slash-stage chain, and verify canonical stage result exists (`aidd/reports/loops/<ticket>/<scope_key>/stage.implement.result.json`).

## Notes
- Implement stage does not run tests; format-only is allowed.

## Additional resources
- Contract schema: [CONTRACT.yaml](CONTRACT.yaml) (when: preflight/postflight or actions contract is unclear; why: validate required fields and artifact expectations before rerun).
