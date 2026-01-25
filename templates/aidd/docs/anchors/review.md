# Anchor: review

## Goals
- Сверить diff с plan/PRD и DoD.
- Вернуть замечания в tasklist (handoff).
- Управлять обязательностью тестов через reviewer marker (если используется).

## RLM Read Policy
- MUST: читать `aidd/reports/research/<ticket>-rlm.pack.*` first.
- PREFER: использовать `rlm-slice` pack для узких запросов.
- MUST NOT: читать `*-rlm.nodes.jsonl` или `*-rlm.links.jsonl` целиком; только spot‑check через `rg`.

## MUST READ FIRST
- git diff / PR diff
- aidd/docs/tasklist/<ticket>.md: AIDD:CONTEXT_PACK, AIDD:CHECKLIST_REVIEW, AIDD:HANDOFF_INBOX
- aidd/docs/spec/<ticket>.spec.yaml (если существует)
- aidd/docs/plan/<ticket>.md: AIDD:FILES_TOUCHED, AIDD:ITERATIONS

## MUST UPDATE
- aidd/docs/tasklist/<ticket>.md: замечания + handoff
- aidd/reports/reviewer/<ticket>.json (review report + маркер тестов)
- AIDD:CONTEXT_PACK → Blockers summary (если есть blocking handoff)
- Каждый finding оформляй как handoff‑задачу в `AIDD:HANDOFF_INBOX` (fact → risk → recommendation + scope/DoD/Boundaries/Tests).
- Формат finding: `scope=iteration_id|n/a`, `blocking: true|false`, DoD/Boundaries/Tests как часть handoff.
- Write surface (разрешено):
  - front‑matter: `Status`, `Updated` (и `Stage`, если есть)
  - `AIDD:CHECKLIST_REVIEW`
  - `AIDD:HANDOFF_INBOX` (через derive)
  - `AIDD:CONTEXT_PACK` (только Status/Stage/Blockers summary)

## MUST NOT
- Рефакторинг “ради красоты”.
- Игнорировать тест‑требования при рисковых изменениях.
- Пропускать проверку исполнимости tasklist (NEXT_3/ITERATIONS_FULL/TEST_EXECUTION).
- Любые правки кода/конфигов/тестов/CI. Review фиксирует только задачи в tasklist.
- Любые изменения вне `aidd/docs/tasklist/<ticket>.md` (кроме автогенерируемых отчётов в `aidd/reports/**`).
- Переписывать `AIDD:ITERATIONS_FULL`, `AIDD:SPEC_PACK`, `AIDD:TEST_EXECUTION`, `AIDD:NEXT_3`.

## Repeat runs
- Повторные `/feature-dev-aidd:review` должны обновлять handoff‑задачи по `id` без дублей (`tasks-derive --source review --append`).

## Output contract
- Status: READY|WARN|BLOCKED
