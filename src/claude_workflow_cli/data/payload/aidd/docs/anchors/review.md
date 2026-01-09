# Anchor: review

## Цели
- Зафиксировать замечания и обновить tasklist.
- Согласовать необходимость тестов через reviewer marker.

## MUST KNOW FIRST
- `aidd/docs/tasklist/<ticket>.md` (AIDD:CONTEXT_PACK + Next 3).
- `aidd/docs/plan/<ticket>.md`.

## Inputs
- Diff/изменения, tasklist, PRD/plan при необходимости.

## Outputs/Contract
- Замечания в tasklist и статус READY/BLOCKED.
- Маркер reviewer в `aidd/reports/reviewer/<ticket>.json` (если нужен тест‑gate).

## MUST UPDATE
- `aidd/docs/tasklist/<ticket>.md`.
- `aidd/docs/.active_stage`.

## MUST NOT
- Требовать full‑read при наличии anchors/working set.

## Blockers
- Отсутствует tasklist или не закрыты критичные замечания.

## Test defaults
- По умолчанию тесты запрашиваются через `claude-workflow reviewer-tests`.
