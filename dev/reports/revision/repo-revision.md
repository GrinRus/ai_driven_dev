# Repository Revision Report

schema: `aidd.repo_revision.v1`
generated_at: `2026-02-24T11:14:09Z`

## Executive summary

- Total nodes: **357**
- Total edges: **935**
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
- Runtime refs: 13
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
  - `skills/aidd-loop/runtime/preflight_prepare.py`
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
- Runtime refs: 12
  - `skills/aidd-docio/runtime/actions_apply.py`
  - `skills/aidd-flow-state/runtime/progress_cli.py`
  - `skills/aidd-flow-state/runtime/set_active_feature.py`
  - `skills/aidd-flow-state/runtime/set_active_stage.py`
  - `skills/aidd-flow-state/runtime/stage_result.py`
  - `skills/aidd-flow-state/runtime/status_summary.py`
  - `skills/aidd-flow-state/runtime/tasklist_check.py`
  - `skills/aidd-flow-state/runtime/tasks_derive.py`
  - `skills/aidd-loop/runtime/preflight_prepare.py`
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
- Runtime refs: 16
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
  - `skills/aidd-loop/runtime/preflight_prepare.py`
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
- Runtime refs: 6
  - `skills/aidd-flow-state/runtime/prd_check.py`
  - `skills/aidd-flow-state/runtime/progress_cli.py`
  - `skills/aidd-flow-state/runtime/set_active_feature.py`
  - `skills/aidd-flow-state/runtime/set_active_stage.py`
  - `skills/aidd-rlm/runtime/rlm_slice.py`
  - `skills/review-spec/runtime/prd_review_cli.py`
- Subagents: `plan-reviewer`, `prd-reviewer`
  - `plan-reviewer` preloads: `aidd-core`, `aidd-policy`, `aidd-rlm`
  - `prd-reviewer` preloads: `aidd-core`, `aidd-policy`, `aidd-rlm`
- Templates: none
- Reachable from root chain: `True`

### `/feature-dev-aidd:spec-interview`
- Skill: `skills/spec-interview/SKILL.md`
- Runtime refs: 4
  - `skills/aidd-flow-state/runtime/set_active_feature.py`
  - `skills/aidd-flow-state/runtime/set_active_stage.py`
  - `skills/aidd-rlm/runtime/rlm_slice.py`
  - `skills/spec-interview/runtime/spec_interview.py`
- Subagents: `spec-interview-writer`
  - `spec-interview-writer` preloads: `aidd-core`, `aidd-policy`, `aidd-rlm`
- Templates:
  - `skills/spec-interview/templates/spec.template.yaml`
- Reachable from root chain: `True`

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
- Preloaded by agents: `analyst`, `implementer`, `plan-reviewer`, `planner`, `prd-reviewer`, `qa`, `researcher`, `reviewer`, `spec-interview-writer`, `tasklist-refiner`, `validator`
- Direct command runtime refs: `implement`, `review`

### `aidd-docio`
- Skill path: `skills/aidd-docio/SKILL.md`
- Preloaded by agents: none
- Direct command runtime refs: `implement`, `qa`, `review`

### `aidd-flow-state`
- Skill path: `skills/aidd-flow-state/SKILL.md`
- Preloaded by agents: none
- Direct command runtime refs: `idea-new`, `implement`, `plan-new`, `qa`, `researcher`, `review`, `review-spec`, `spec-interview`, `tasks-new`

### `aidd-loop`
- Skill path: `skills/aidd-loop/SKILL.md`
- Preloaded by agents: `implementer`, `qa`, `reviewer`
- Direct command runtime refs: `implement`, `qa`, `review`

### `aidd-observability`
- Skill path: `skills/aidd-observability/SKILL.md`
- Preloaded by agents: none
- Direct command runtime refs: none

### `aidd-policy`
- Skill path: `skills/aidd-policy/SKILL.md`
- Preloaded by agents: `analyst`, `implementer`, `plan-reviewer`, `planner`, `prd-reviewer`, `qa`, `researcher`, `reviewer`, `spec-interview-writer`, `tasklist-refiner`, `validator`
- Direct command runtime refs: none

### `aidd-rlm`
- Skill path: `skills/aidd-rlm/SKILL.md`
- Preloaded by agents: `analyst`, `plan-reviewer`, `planner`, `prd-reviewer`, `researcher`, `reviewer`, `spec-interview-writer`, `tasklist-refiner`, `validator`
- Direct command runtime refs: `idea-new`, `implement`, `plan-new`, `qa`, `researcher`, `review`, `review-spec`, `spec-interview`, `tasks-new`

### `aidd-stage-research`
- Skill path: `skills/aidd-stage-research/SKILL.md`
- Preloaded by agents: `researcher`
- Direct command runtime refs: none

## Unused triage

### Safe-to-delete

- none

### Candidates

- none

## Cleanup plan

- none

Validation commands:
- `python3 tests/repo_tools/repo_topology_audit.py --repo-root . --output-json dev/reports/revision/repo-revision.graph.json --output-md dev/reports/revision/repo-revision.md --output-cleanup dev/reports/revision/repo-cleanup-plan.json`
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
  - `doc_ref_runtime`: 332
  - `hook_event_to_hook`: 16
  - `hook_ref_runtime`: 5
  - `runtime_dynamic_load`: 7
  - `runtime_import`: 241
  - `skill_runtime_ref`: 114
  - `skill_template_ref`: 10
  - `test_ref_runtime`: 164
