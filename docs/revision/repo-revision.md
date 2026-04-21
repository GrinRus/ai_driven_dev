# Repository Revision Report

> INTERNAL/DEV-ONLY: generated maintainer report for repository topology and cleanup planning.

Owner: feature-dev-aidd
Last reviewed: 2026-04-13
Status: active

schema: `aidd.repo_revision.v1`
generated_at: `2026-04-13T12:22:37Z`

## Executive summary

- Total nodes: **408**
- Total edges: **835**
- User-invocable commands: **11**
- Reachable runtimes from command chain: **90**
- Detached agents: **0**

Key findings:
- No candidate findings from current graph/triage run.

## Topology matrix

### `/feature-dev-aidd:aidd-init`
- Skill: `skills/aidd-init/SKILL.md`
- Runtime refs: 1
  - `skills/aidd-init/runtime/init.py`
- Subagents: none
- Templates: none
- Reachable from root chain: `True`

### `/feature-dev-aidd:idea-new`
- Skill: `skills/idea-new/SKILL.md`
- Runtime refs: 4
  - `skills/aidd-flow-state/runtime/set_active_feature.py`
  - `skills/aidd-flow-state/runtime/set_active_stage.py`
  - `skills/aidd-rlm/runtime/rlm_slice.py`
  - `skills/idea-new/runtime/analyst_check.py`
- Subagents: `analyst`
  - `analyst` preloads: `aidd-core`, `aidd-policy`, `aidd-rlm`
- Templates:
  - `skills/idea-new/templates/prd.template.md`
- Reachable from root chain: `True`

### `/feature-dev-aidd:implement`
- Skill: `skills/implement/SKILL.md`
- Runtime refs: 12
  - `skills/aidd-core/runtime/diff_boundary_check.py`
  - `skills/aidd-docio/runtime/actions_apply.py`
  - `skills/aidd-flow-state/runtime/prd_check.py`
  - `skills/aidd-flow-state/runtime/progress_cli.py`
  - `skills/aidd-flow-state/runtime/set_active_feature.py`
  - `skills/aidd-flow-state/runtime/set_active_stage.py`
  - `skills/aidd-flow-state/runtime/stage_result.py`
  - `skills/aidd-flow-state/runtime/status_summary.py`
  - `skills/aidd-flow-state/runtime/tasklist_check.py`
  - `skills/aidd-loop/runtime/loop_pack.py`
  - `skills/aidd-rlm/runtime/rlm_slice.py`
  - `skills/implement/runtime/implement_run.py`
- Subagents: `implementer`
  - `implementer` preloads: `aidd-core`, `aidd-loop`, `aidd-policy`
- Templates: none
- Reachable from root chain: `True`

### `/feature-dev-aidd:plan-new`
- Skill: `skills/plan-new/SKILL.md`
- Runtime refs: 5
  - `skills/aidd-flow-state/runtime/prd_check.py`
  - `skills/aidd-flow-state/runtime/set_active_feature.py`
  - `skills/aidd-flow-state/runtime/set_active_stage.py`
  - `skills/aidd-rlm/runtime/rlm_slice.py`
  - `skills/plan-new/runtime/research_check.py`
- Subagents: `planner`, `validator`
  - `planner` preloads: `aidd-core`, `aidd-policy`, `aidd-rlm`
  - `validator` preloads: `aidd-core`, `aidd-policy`, `aidd-rlm`
- Templates:
  - `skills/plan-new/templates/plan.template.md`
- Reachable from root chain: `True`

### `/feature-dev-aidd:qa`
- Skill: `skills/qa/SKILL.md`
- Runtime refs: 11
  - `skills/aidd-docio/runtime/actions_apply.py`
  - `skills/aidd-flow-state/runtime/progress_cli.py`
  - `skills/aidd-flow-state/runtime/set_active_feature.py`
  - `skills/aidd-flow-state/runtime/set_active_stage.py`
  - `skills/aidd-flow-state/runtime/stage_result.py`
  - `skills/aidd-flow-state/runtime/status_summary.py`
  - `skills/aidd-flow-state/runtime/tasklist_check.py`
  - `skills/aidd-flow-state/runtime/tasks_derive.py`
  - `skills/aidd-rlm/runtime/rlm_slice.py`
  - `skills/qa/runtime/qa.py`
  - `skills/qa/runtime/qa_run.py`
- Subagents: `qa`
  - `qa` preloads: `aidd-core`, `aidd-loop`, `aidd-policy`
- Templates: none
- Reachable from root chain: `True`

### `/feature-dev-aidd:researcher`
- Skill: `skills/researcher/SKILL.md`
- Runtime refs: 5
  - `skills/aidd-flow-state/runtime/set_active_feature.py`
  - `skills/aidd-flow-state/runtime/set_active_stage.py`
  - `skills/aidd-flow-state/runtime/tasks_derive.py`
  - `skills/aidd-rlm/runtime/rlm_finalize.py`
  - `skills/researcher/runtime/research.py`
- Subagents: `researcher`
  - `researcher` preloads: `aidd-core`, `aidd-policy`, `aidd-rlm`, `aidd-stage-research`
- Templates:
  - `skills/researcher/templates/research.template.md`
- Reachable from root chain: `True`

### `/feature-dev-aidd:review`
- Skill: `skills/review/SKILL.md`
- Runtime refs: 15
  - `skills/aidd-core/runtime/diff_boundary_check.py`
  - `skills/aidd-docio/runtime/actions_apply.py`
  - `skills/aidd-flow-state/runtime/progress_cli.py`
  - `skills/aidd-flow-state/runtime/set_active_feature.py`
  - `skills/aidd-flow-state/runtime/set_active_stage.py`
  - `skills/aidd-flow-state/runtime/stage_result.py`
  - `skills/aidd-flow-state/runtime/status_summary.py`
  - `skills/aidd-flow-state/runtime/tasklist_check.py`
  - `skills/aidd-flow-state/runtime/tasks_derive.py`
  - `skills/aidd-loop/runtime/loop_pack.py`
  - `skills/aidd-rlm/runtime/rlm_slice.py`
  - `skills/review/runtime/review_pack.py`
  - `skills/review/runtime/review_report.py`
  - `skills/review/runtime/review_run.py`
  - `skills/review/runtime/reviewer_tests.py`
- Subagents: `reviewer`
  - `reviewer` preloads: `aidd-core`, `aidd-loop`, `aidd-policy`, `aidd-rlm`
- Templates: none
- Reachable from root chain: `True`

### `/feature-dev-aidd:review-spec`
- Skill: `skills/review-spec/SKILL.md`
- Runtime refs: 7
  - `skills/aidd-core/runtime/plan_review_gate.py`
  - `skills/aidd-core/runtime/prd_review.py`
  - `skills/aidd-flow-state/runtime/prd_check.py`
  - `skills/aidd-flow-state/runtime/progress_cli.py`
  - `skills/aidd-flow-state/runtime/set_active_feature.py`
  - `skills/aidd-flow-state/runtime/set_active_stage.py`
  - `skills/aidd-rlm/runtime/rlm_slice.py`
- Subagents: `plan-reviewer`, `prd-reviewer`
  - `plan-reviewer` preloads: `aidd-core`, `aidd-policy`, `aidd-rlm`
  - `prd-reviewer` preloads: `aidd-core`, `aidd-policy`, `aidd-rlm`
- Templates: none
- Reachable from root chain: `True`

### `/feature-dev-aidd:spec-interview`
- Historical note: stage removed from active planning flow in Wave 149.
- Current status: archived, not reachable from root chain, runtime/template assets removed from repository.

### `/feature-dev-aidd:status`
- Skill: `skills/status/SKILL.md`
- Runtime refs: 2
  - `skills/status/runtime/index_sync.py`
  - `skills/status/runtime/status.py`
- Subagents: none
- Templates: none
- Reachable from root chain: `True`

### `/feature-dev-aidd:tasks-new`
- Skill: `skills/tasks-new/SKILL.md`
- Runtime refs: 6
  - `skills/aidd-flow-state/runtime/prd_check.py`
  - `skills/aidd-flow-state/runtime/set_active_feature.py`
  - `skills/aidd-flow-state/runtime/set_active_stage.py`
  - `skills/aidd-flow-state/runtime/tasklist_check.py`
  - `skills/aidd-rlm/runtime/rlm_slice.py`
  - `skills/tasks-new/runtime/tasks_new.py`
- Subagents: `tasklist-refiner`
  - `tasklist-refiner` preloads: `aidd-core`, `aidd-policy`, `aidd-rlm`
- Templates:
  - `skills/tasks-new/templates/tasklist.template.md`
- Reachable from root chain: `True`

## Shared skills coverage

### `aidd-core`
- Skill path: `skills/aidd-core/SKILL.md`
- Preloaded by agents: `analyst`, `implementer`, `plan-reviewer`, `planner`, `prd-reviewer`, `qa`, `researcher`, `reviewer`, `tasklist-refiner`, `validator`
- Direct command runtime refs: `implement`, `review`, `review-spec`

### `aidd-docio`
- Skill path: `skills/aidd-docio/SKILL.md`
- Preloaded by agents: none
- Direct command runtime refs: `implement`, `qa`, `review`

### `aidd-flow-state`
- Skill path: `skills/aidd-flow-state/SKILL.md`
- Preloaded by agents: none
- Direct command runtime refs: `idea-new`, `implement`, `plan-new`, `qa`, `researcher`, `review`, `review-spec`, `tasks-new`

### `aidd-loop`
- Skill path: `skills/aidd-loop/SKILL.md`
- Preloaded by agents: `implementer`, `qa`, `reviewer`
- Direct command runtime refs: `implement`, `review`

### `aidd-observability`
- Skill path: `skills/aidd-observability/SKILL.md`
- Preloaded by agents: none
- Direct command runtime refs: none

### `aidd-policy`
- Skill path: `skills/aidd-policy/SKILL.md`
- Preloaded by agents: `analyst`, `implementer`, `plan-reviewer`, `planner`, `prd-reviewer`, `qa`, `researcher`, `reviewer`, `tasklist-refiner`, `validator`
- Direct command runtime refs: none

### `aidd-rlm`
- Skill path: `skills/aidd-rlm/SKILL.md`
- Preloaded by agents: `analyst`, `plan-reviewer`, `planner`, `prd-reviewer`, `researcher`, `reviewer`, `tasklist-refiner`, `validator`
- Direct command runtime refs: `idea-new`, `implement`, `plan-new`, `qa`, `researcher`, `review`, `review-spec`, `tasks-new`

### `aidd-stage-research`
- Skill path: `skills/aidd-stage-research/SKILL.md`
- Preloaded by agents: `researcher`
- Direct command runtime refs: none

## Unused triage

### Safe-to-delete

- `docs/runtime-module-decomposition-plan.md`: action=`delete`, confidence=`high`, risk=`low`
  - reason: no inbound references in graph or textual mentions

### Candidates

- none

## Cleanup plan

1. `docs/runtime-module-decomposition-plan.md` -> `delete` (risk: `low`)
   - reason: no inbound references in graph or textual mentions

Validation commands:
- `python3 tests/repo_tools/repo_topology_audit.py --repo-root . --output-json docs/revision/repo-revision.graph.json --output-md docs/revision/repo-revision.md --output-cleanup docs/revision/repo-cleanup-plan.json`
- `tests/repo_tools/ci-lint.sh`
- `tests/repo_tools/smoke-workflow.sh`

## Appendix

- Sources of truth:
  - `agents_glob`: `agents/*.md`
  - `hooks_wiring`: `hooks/hooks.json`
  - `plugin_registry`: `.claude-plugin/plugin.json`
  - `runtime_glob`: `skills/*/runtime/**/*.py`
  - `skills_glob`: `skills/*/SKILL.md`
  - `template_seed_map`: `skills/aidd-init/runtime/init.py:SKILL_TEMPLATE_SEEDS`
- Edge types:
  - `agent_preload_skill`: 35
  - `command_subagent`: 11
  - `doc_ref_runtime`: 184
  - `hook_event_to_hook`: 16
  - `hook_ref_runtime`: 5
  - `runtime_dynamic_load`: 8
  - `runtime_import`: 242
  - `skill_runtime_ref`: 112
  - `skill_template_ref`: 10
  - `test_ref_runtime`: 212
