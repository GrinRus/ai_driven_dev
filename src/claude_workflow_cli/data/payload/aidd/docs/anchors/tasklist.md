# Anchor: tasklist

## Цели
- Создать tasklist с `Next 3`, handoff и AIDD‑anchors.
- Синхронизировать чеклисты с планом и PRD.

## MUST KNOW FIRST
- `aidd/docs/plan/<ticket>.md`.
- `aidd/docs/prd/<ticket>.prd.md`.
- `aidd/docs/tasklist/template.md`.

## Inputs
- План и PRD после review.

## Outputs/Contract
- `aidd/docs/tasklist/<ticket>.md` со статусом `READY`.
- Заполненные AIDD‑anchors (контекст, next3, вопросы, риски).

## MUST UPDATE
- `aidd/docs/tasklist/<ticket>.md`.
- `aidd/docs/.active_stage`.

## MUST NOT
- Создавать tasklist без ссылок на PRD/Plan/Research.

## Blockers
- Нет `Plan Review READY` или `PRD Review READY`.
