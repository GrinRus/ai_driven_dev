# Anchor: spec-interview

## Goals
- Run a deep interview at top level (AskUserQuestionTool) and record the log.
- Produce `aidd/docs/spec/<ticket>.spec.yaml` as the canonical spec (optional step).
- Tasklist updates happen only via `/tasks-new`.
- Закрыть decision points по ближайшим `iteration_id` из плана.

## MUST READ FIRST
- aidd/docs/plan/<ticket>.md
- aidd/docs/prd/<ticket>.prd.md
- aidd/docs/research/<ticket>.md

## MUST UPDATE
- aidd/docs/spec/<ticket>.spec.yaml
- aidd/reports/spec/<ticket>.interview.jsonl (append-only)

## MUST NOT
- Do not call AskUserQuestionTool from subagents.

## Interview rules (non-obvious)
- No questions that are already answered in plan/PRD/research/tasklist.
- Each question must affect UX, contracts, data, tests, rollout, or observability.
- Each question must map to a spec section **and** to `iteration_id` (I1/I2/...) when applicable.
- Provide: Why/Impact + Options + Default.

## Definition of Done
- Spec status is READY (если закрыты decision points для ближайших итераций).
- Blocker open questions are empty (если spec доведён до READY).
- Tasklist синхронизируется отдельно через `/tasks-new`.
