---
name: aidd-flow-state
description: Shared flow/state runtime ownership for stage state, progress/tasklist, and stage-result lifecycle.
lang: en
model: inherit
user-invocable: false
---

## Scope
- This skill owns shared flow/state runtime entrypoints.
- Stage skills call these commands for active stage/feature state, progress checks, tasklist normalization, and stage-result/status lifecycle.
- DocIO and loop orchestration ownership remains in `feature-dev-aidd:aidd-docio` and `feature-dev-aidd:aidd-loop`.

## Canonical shared Python entrypoints
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_feature.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_stage.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/prd_check.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/progress.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/progress_cli.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/tasklist_check.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/tasks_derive.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/stage_result.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/status_summary.py`

## Ownership guard
- Flow/state command runtime modules must live under `skills/aidd-flow-state/runtime/*`.
- Consumers should use `skills/aidd-flow-state/runtime/*` as canonical command paths.

## Additional resources
- [references/progress-tasklist.md](references/progress-tasklist.md) (when: progress/tasklist checks are unclear; why: align check/normalize and logging semantics).
- [references/stage-lifecycle.md](references/stage-lifecycle.md) (when: stage result/status flow is unclear; why: keep stage-result and summary updates deterministic).
