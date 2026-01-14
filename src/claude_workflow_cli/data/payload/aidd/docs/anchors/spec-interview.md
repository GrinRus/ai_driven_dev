# Anchor: spec-interview

## Goals
- Run a deep interview at top level (AskUserQuestionTool) and record the log.
- Produce `aidd/docs/spec/<ticket>.spec.yaml` as the canonical spec (optional step).
- Update tasklist summary sections (`AIDD:SPEC_PACK`, `AIDD:TEST_STRATEGY`) if tasklist exists.

## MUST READ FIRST
- aidd/docs/plan/<ticket>.md
- aidd/docs/prd/<ticket>.prd.md
- aidd/docs/research/<ticket>.md
- aidd/docs/tasklist/<ticket>.md (AIDD:CONTEXT_PACK + AIDD:NEXT_3) if exists

## MUST UPDATE
- aidd/docs/spec/<ticket>.spec.yaml
- aidd/reports/spec/<ticket>.interview.jsonl (append-only)
- aidd/docs/tasklist/<ticket>.md (AIDD:SPEC_PACK + AIDD:TEST_STRATEGY) if exists

## MUST NOT
- Do not call AskUserQuestionTool from subagents.

## Interview rules (non-obvious)
- No questions that are already answered in plan/PRD/research/tasklist.
- Each question must affect UX, contracts, data, tests, rollout, or observability.
- Provide: Why/Impact + Options + Default.

## Definition of Done
- Spec status is READY (если цель — закрыть интервью).
- Blocker open questions are empty (если spec доведён до READY).
- Tasklist summary updated from spec (если tasklist существует).
