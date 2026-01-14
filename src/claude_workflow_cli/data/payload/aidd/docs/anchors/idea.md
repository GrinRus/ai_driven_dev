# Anchor: idea

## Goals
- Создать/обновить PRD draft.
- Заполнить AIDD:RESEARCH_HINTS (пути/ключевые слова/заметки).
- Сформировать вопросы пользователю; без ответов статус не READY.

## MUST READ FIRST
- aidd/docs/prd/<ticket>.prd.md: AIDD:RESEARCH_HINTS, AIDD:OPEN_QUESTIONS, Диалог analyst
- aidd/docs/.active_ticket и .active_feature

## MUST UPDATE
- aidd/docs/prd/<ticket>.prd.md: PRD draft + вопросы + AIDD:RESEARCH_HINTS

## MUST NOT
- Ставить READY без ответов пользователя.
- Уходить в код до research/plan/tasklist.

## Output contract
- PRD статус: PENDING/BLOCKED до ответов.
- Следующий шаг: /researcher <ticket>.
