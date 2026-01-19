# Anchor: idea

## Goals
- Создать/обновить PRD draft.
- Заполнить AIDD:RESEARCH_HINTS (пути/ключевые слова/заметки).
- Сформировать вопросы пользователю; без ответов статус не READY.
- Если ответы пришли в чате — зафиксировать их в `AIDD:ANSWERS`.
- В `AIDD:OPEN_QUESTIONS` использовать `Q1/Q2/...` для ссылок из плана.

## MUST READ FIRST
- aidd/docs/prd/<ticket>.prd.md: AIDD:RESEARCH_HINTS, AIDD:OPEN_QUESTIONS, AIDD:ANSWERS, Диалог analyst
- aidd/docs/.active_ticket и .active_feature

## MUST UPDATE
- aidd/docs/prd/<ticket>.prd.md: PRD draft + вопросы + AIDD:RESEARCH_HINTS + AIDD:ANSWERS

## MUST NOT
- Ставить READY без ответов пользователя.
- Уходить в код до research/plan/tasklist.

## Output contract
- PRD статус: PENDING/BLOCKED до ответов.
- Следующий шаг: /feature-dev-aidd:researcher <ticket>.
