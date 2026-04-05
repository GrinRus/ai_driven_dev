# Runtime Module Decomposition Plan

> INTERNAL/DEV-ONLY: phased refactor plan for oversized runtime modules.

## Scope

This plan covers modules reported by `tests/repo_tools/runtime-module-guard.py`
with `>600` LOC warnings. Goal: split large files into cohesive parts without
changing runtime behavior, CLI contracts, or report schemas.

Snapshot (2026-04-05):
- `skills/aidd-core/runtime/qa_agent.py` (623)
- `skills/aidd-core/runtime/research_guard.py` (827)
- `skills/aidd-core/runtime/runtime.py` (745)
- `skills/aidd-flow-state/runtime/progress.py` (779)
- `skills/aidd-flow-state/runtime/stage_result.py` (641)
- `skills/aidd-loop/runtime/loop_step_stage_chain.py` (765)
- `skills/aidd-loop/runtime/preflight_prepare.py` (716)
- `skills/aidd-rlm/runtime/rlm_nodes_build.py` (624)
- `skills/researcher/runtime/research.py` (826)
- `skills/review/runtime/review_pack.py` (743)

## Non-Goals

- No feature work.
- No public CLI/API argument changes.
- No compatibility alias removals.
- No schema version bumps.

## Decomposition Rules

- Keep entrypoint files stable; extract helpers into `*_parts/` modules.
- Move pure functions first, then side-effectful orchestration.
- Preserve import surface in entrypoint files.
- Add or update focused tests before and after each extraction step.
- Keep each PR behavior-neutral and small enough for quick rollback.

## Execution Waves

1. Wave A (lowest coupling):
- `skills/aidd-rlm/runtime/rlm_nodes_build.py`
- `skills/review/runtime/review_pack.py`
- `skills/aidd-flow-state/runtime/stage_result.py`

1. Wave B (medium coupling):
- `skills/aidd-core/runtime/qa_agent.py`
- `skills/aidd-flow-state/runtime/progress.py`
- `skills/aidd-loop/runtime/preflight_prepare.py`

1. Wave C (highest coupling / core orchestration):
- `skills/aidd-core/runtime/research_guard.py`
- `skills/aidd-core/runtime/runtime.py`
- `skills/aidd-loop/runtime/loop_step_stage_chain.py`
- `skills/researcher/runtime/research.py`

## Validation Per PR

- `ruff check . --select F401,F841,B007,B023,ERA,F811`
- `python3 tests/repo_tools/runtime-module-guard.py`
- `python3 tests/repo_tools/release_guard.py --root .`
- `python3 tests/repo_tools/release_docs_guard.py --root .`
- `tests/repo_tools/ci-lint.sh`
- `tests/repo_tools/smoke-workflow.sh`

## Exit Criteria

- No module remains above warning threshold without an explicit waiver.
- Entry-point behavior remains unchanged (existing tests green).
- Refactor history is split into reversible, owner-reviewed PRs.
