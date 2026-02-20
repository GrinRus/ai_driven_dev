# Stage Lexicon (AIDD)

Этот документ фиксирует единый словарь стадий для workflow и runtime.

## Public stages (user-facing)
- `idea`
- `research`
- `plan`
- `review-spec`
- `spec-interview` (optional)
- `tasklist`
- `implement`
- `review`
- `qa`
- `status`

## Internal stages (runtime/internal gates)
- `review-plan`
- `review-prd`

## Legacy aliases (normalized to canonical stages)
- `spec` -> `spec-interview`
- `tasks`/`task` -> `tasklist`

## Mapping rules
- `review-spec` — umbrella stage:
  - сначала `review-plan`
  - затем `review-prd`
- В пользовательских сценариях и документации по умолчанию используйте `review-spec`.
- В runtime/gates допускается детализация через `review-plan` и `review-prd`.

## Artifact expectations (summary)
- Все стадии читают/пишут только в workspace `aidd/**`.
- Planning flow (`idea/research/plan/review-spec/spec-interview/tasklist`) создаёт/обновляет docs:
  - `aidd/docs/prd/<ticket>.prd.md`
  - `aidd/docs/research/<ticket>.md`
  - `aidd/docs/plan/<ticket>.md`
  - `aidd/docs/tasklist/<ticket>.md`
- Loop flow (`implement/review/qa/status`) опирается на reports:
  - `aidd/reports/loops/**`
  - `aidd/reports/reviewer/**`
  - `aidd/reports/qa/**`
  - `aidd/reports/actions/**`

## Path policy
- Stage-specific entrypoints: `skills/<stage>/runtime/*.py` (canonical Python-only).
- Shared entrypoints: canonical `skills/aidd-core/runtime/*.py`, `skills/aidd-docio/runtime/*.py`, `skills/aidd-flow-state/runtime/*.py`, `skills/aidd-loop/runtime/*.py`.
- `tools/*.sh` и stage shell wrappers не входят в runtime-path и не используются для stage orchestration.
