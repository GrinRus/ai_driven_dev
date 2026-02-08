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
- Stage-specific entrypoints: `skills/<stage>/scripts/*` (canonical).
- Shared entrypoints: target canonical `skills/aidd-core/scripts/*`.
- Legacy `tools/*.sh` допускаются только как compatibility shims в migration window.
