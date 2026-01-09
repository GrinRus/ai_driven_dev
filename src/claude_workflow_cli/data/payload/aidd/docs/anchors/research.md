# Anchor: research

## Цели
- Обновить `aidd/reports/research/*` и документ исследования.
- Зафиксировать интеграционные точки, reuse, риски и команды.

## MUST KNOW FIRST
- `aidd/docs/prd/<ticket>.prd.md` (особенно `## Research Hints`).
- `aidd/docs/research/template.md`.
- `aidd/docs/anchors/research.md`.

## Inputs
- PRD + Research Hints.
- Репозиторий, конвенции, code index.

## Outputs/Contract
- `aidd/docs/research/<ticket>.md` со статусом `reviewed|pending`.
- `aidd/reports/research/<ticket>-context.json` и `aidd/reports/research/<ticket>-targets.json`.
- Опционально: `aidd/reports/research/<ticket>-call-graph-full.json`.

## MUST UPDATE
- `aidd/docs/research/<ticket>.md`.
- `aidd/reports/research/<ticket>-context.json` (и targets).

## MUST NOT
- Пропускать фиксацию интеграционных точек и рисков.
- Задавать вопросы без списка просмотренных артефактов.

## Blockers
- Недостаточно данных для baseline (нет путей/keywords).
