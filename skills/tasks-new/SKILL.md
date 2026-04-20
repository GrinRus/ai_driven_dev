---
name: tasks-new
description: Derives or refines tasklist items from PRD and plan artifacts. Use when tasklist stage prepares implementation-ready work items. Do not use when the request is plan authoring in `plan-new` or loop execution in `implement`.
argument-hint: $1 [note...]
lang: en
prompt_version: 1.1.27
source_version: 1.1.27
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg *)"
  - "Bash(sed *)"
  - "Bash(cat *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/tasks-new/runtime/tasks_new.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_stage.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_feature.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/prd_check.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_slice.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/tasklist_check.py *)"
model: inherit
disable-model-invocation: true
user-invocable: true
---

Follow `feature-dev-aidd:aidd-core`.

## Steps
1. Inputs: resolve active feature and verify PRD/plan artifacts needed for tasklist generation.
2. Preflight: set active stage `tasklist` and active feature.
3. Orchestration is bounded: run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/tasks-new/runtime/tasks_new.py --ticket <ticket>`, then gate PRD readiness with `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/prd_check.py`.
4. Use the existing rolling context pack as input evidence; do not invoke standalone context-pack builder scripts from this stage.
5. Treat `feature-dev-aidd:tasklist-refiner` only as repair guidance under this stage policy; do not invoke it as a runtime subagent. Any repairable refinement must still obey validator output as contract and must not introduce prose-labeled or shell-chained commands into `AIDD:TEST_EXECUTION`.
6. After any repair pass, rerun `python3 ${CLAUDE_PLUGIN_ROOT}/skills/tasks-new/runtime/tasks_new.py --ticket <ticket>` once to rematerialize contract-owned sections, especially `AIDD:TEST_EXECUTION`, before final postflight validation.
7. Postflight: validate via `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/tasklist_check.py`.
8. Retry policy: allow at most one bounded retry, and only when validator issues are categorized as `repairable_structure`. Do not retry for `upstream_blocker`, env/policy errors, or truth/advisory warnings.
9. Forbidden recovery paths in this stage: creating missing upstream artifacts, launching ad hoc repair interviews, reading runtime source files for self-diagnosis, or looping `tasks_new.py -> tasklist_check.py -> manual edits` without new evidence.
10. Ready path: return `/feature-dev-aidd:implement <ticket>` only when `tasklist_check.py` passes and the next iteration is implementation-ready.
11. Pending or blocked path: return the output contract with structured tasklist gaps and a canonical next action on `review-spec` or `tasks-new`; stop after the bounded retry budget is exhausted.

## Command contracts
### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/tasks-new/runtime/tasks_new.py`
- When to run: as canonical tasklist stage entrypoint before implement phase.
- Inputs: `--ticket <ticket>` and current PRD/plan artifacts.
- Outputs: normalized tasklist structure, contract-owned test execution materialization, and structured validator issue set.
- Failure mode: non-zero exit when upstream blockers exist or tasklist contract checks fail.
- Next action: rerun only after fixing upstream readiness blockers, or do one bounded retry for `repairable_structure`; after any refiner pass, rerun this entrypoint before final validator check.

## Notes
- Planning stage: `AIDD:ACTIONS_LOG: n/a`.

## Additional resources
- Tasklist template source: [templates/tasklist.template.md](templates/tasklist.template.md) (when: generating or normalizing tasklist sections; why: keep iteration/handoff structure aligned with canonical template).
