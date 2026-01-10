# Anchor: research

## Goals
- Собрать подтверждённые integration points, reuse, risks, test hooks.
- Обновить research report и дать handoff в tasklist.
- Status reviewed — только при воспроизводимом сборе (commands + paths).

## MUST READ FIRST
- aidd/docs/prd/<ticket>.prd.md: AIDD:RESEARCH_HINTS
- aidd/reports/research/<ticket>-context.json (или актуальный путь)
- aidd/docs/research/<ticket>.md (если существует)

## MUST UPDATE
- aidd/docs/research/<ticket>.md:
  - AIDD:INTEGRATION_POINTS
  - AIDD:REUSE_CANDIDATES
  - AIDD:RISKS
  - AIDD:TEST_HOOKS
  - Commands run / paths

## MUST NOT
- Писать “возможно” без файлов/команд.
- Вставлять большие JSON — только ссылки.

## Output contract
- Status: reviewed|pending
- Handoff: задачи формата "Research: ..." (source: aidd/reports/research/...).
