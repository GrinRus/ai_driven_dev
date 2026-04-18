---
name: implement
description: Executes implement-stage loop workflow for the next scoped work item through stage-chain orchestration. Use when implement stage enters loop mode. Do not use when the request is focused on findings validation in `review` or verification/reporting in `qa`.
argument-hint: $1 [note...] [test=fast|targeted|full|none] [tests=<filters>] [tasks=<task1,task2>]
lang: en
prompt_version: 1.1.54
source_version: 1.1.54
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
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
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_stage.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/prd_check.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_pack.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/runtime/diff_boundary_check.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_slice.py *)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/hooks/format-and-test.sh *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/progress_cli.py *)"
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

Shared loop-stage contract: [../aidd-loop/stage-skill-contract.md](../aidd-loop/stage-skill-contract.md).

## Steps
1. Resolve active `<ticket>/<scope_key>` and read in order: `readmap.md` -> loop pack -> latest review pack when present -> rolling context pack.
2. Apply the shared loop-stage contract: canonical stage-chain only, internal preflight/postflight stay orchestration-only details, and manual write/create of `stage.implement.result.json` is forbidden. `[AIDD_LOOP_POLICY:MANUAL_STAGE_RESULT_FORBIDDEN]`
3. Run subagent `feature-dev-aidd:implementer`, Fill actions.json for the current bounded work item at `aidd/reports/actions/<ticket>/<scope_key>/implement.actions.json`, and validate it via `python3 ${CLAUDE_PLUGIN_ROOT}/skills/implement/runtime/implement_run.py`.
4. Canonical stage-chain is `internal preflight -> stage runtime -> actions_apply.py/postflight -> python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/stage_result.py`; the only valid stage result path is `aidd/reports/loops/<ticket>/<scope_key>/stage.implement.result.json`. `[AIDD_LOOP_POLICY:CANONICAL_STAGE_RESULT_PATH]`
5. Non-canonical stage-result paths under `skills/aidd-loop/runtime/` are forbidden. `[AIDD_LOOP_POLICY:NON_CANONICAL_STAGE_RESULT_FORBIDDEN]`
6. If stdout/stderr contains `can't open file .../skills/.../runtime/...`, stop with BLOCKED `runtime_path_missing_or_drift`; do not invent alternate filenames or manual recovery paths.
7. Return one terminal payload with updated evidence and the next canonical handoff.

## Command contracts
### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/implement/runtime/implement_run.py`
- When to run: as canonical implement stage runtime before postflight.
- Inputs: ticket, scope/work-item context, and validated actions payload.
- Outputs: stage validation artifacts and status payload for downstream postflight.
- Failure mode: non-zero exit for invalid actions schema or missing stage prerequisites.
- Next action: fix actions/preconditions and rerun runtime validation before postflight.

### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-docio/runtime/actions_apply.py`
- When to run: mandatory final step in stage-chain postflight after actions validation.
- Inputs: `--actions <path>` and optional `--apply-log <path>`.
- Outputs: applied actions, progress/status artifacts, and apply logs.
- Failure mode: DocOps apply failure, boundary guard failure, or status-summary failure.
- Next action: inspect action/apply logs, fix root cause, rerun the stage-chain, and verify canonical stage result exists (`aidd/reports/loops/<ticket>/<scope_key>/stage.implement.result.json`).

### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/stage_result.py`
- When to run: stage-chain postflight stage-result emission only (not operator/manual recovery command).
- Inputs: canonical postflight payload (`ticket`, `stage`, `result`, `scope-key`, `work-item-key`, evidence links).
- Outputs: canonical `aidd.stage_result.v1` at `aidd/reports/loops/<ticket>/<scope_key>/stage.implement.result.json`.
- Failure mode: non-zero exit on missing required args or invalid stage-result contract fields.
- Next action: fix postflight payload generation and rerun the stage-chain; do not switch to non-canonical loop runtime paths.

## Additional resources
- Shared loop-stage contract: [../aidd-loop/stage-skill-contract.md](../aidd-loop/stage-skill-contract.md) (when: shared stage-chain/read-order/fail-fast rules are needed; why: keep common loop-stage policy in one canonical file).
- Shared loop reference: [../aidd-loop/reference.md](../aidd-loop/reference.md) (when: shared stage-chain paths or loop invariants are unclear; why: reuse one canonical loop reference instead of duplicating command lore).
- Contract schema: [CONTRACT.yaml](CONTRACT.yaml) (when: preflight/postflight or actions contract is unclear; why: validate required fields and artifact expectations before rerun).
