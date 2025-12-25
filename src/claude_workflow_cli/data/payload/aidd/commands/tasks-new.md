---
description: "Сформировать чеклист задач (aidd/docs/tasklist/`<ticket>`.md) для фичи"
argument-hint: "<TICKET> [note...]"
lang: ru
prompt_version: 1.0.1
source_version: 1.0.1
allowed-tools:
  - Read
  - Edit
  - Write
  - Grep
  - Glob
model: inherit
disable-model-invocation: false
---

## Контекст
Команда`/tasks-new`создаёт рабочий чеклист`aidd/docs/tasklist/`<ticket>`.md`на основе утверждённого плана. Tasklist фиксирует критерии прогресса для`/implement`,`/review`,`/qa`и контролируется`gate-workflow`. Свободный ввод после тикета включи как примечание/контекст в чеклист.

## Входные артефакты
- @aidd/docs/plan/`<ticket>`.md — список итераций, DoD, зависимостей.
- @aidd/docs/prd/`<ticket>`.prd.md + раздел`## PRD Review`(action items).
- @aidd/docs/research/`<ticket>`.md — reuse и риски.
- Шаблон @templates/tasklist.md (если файл создаётся с нуля).

## Когда запускать
- Сразу после`/plan-new`(validator PASS). Повторно — когда нужно пересобрать чеклист после изменения плана/PRD.

## Автоматические хуки и переменные
-`gate-workflow`проверяет, что tasklist существует и содержит актуальные`- [x]`.
- Пресет`feature-impl`(`claude-presets/feature-impl.yaml`) может заполнить типовые задачи.

## Что редактируется
-`aidd/docs/tasklist/`<ticket>`.md`: фронт-маттер (Ticket, Slug hint, Feature, Status, PRD/Plan/Research ссылки, Updated), разделы 1–6 и памятка «Как отмечать прогресс».

## Пошаговый план
1. Создай/открой`aidd/docs/tasklist/`<ticket>`.md`. При отсутствии файла скопируй`templates/tasklist.md`.
2. Обнови фронт-маттер Данными тикета и текущей даты (`Updated`).
3. Перенеси этапы из плана: аналитика, реализация, QA, релиз, пострелиз. Добавь конкретные чекбоксы с владельцами и результатами.
4. Вынеси все action items из`## PRD Review`в отдельные чекбоксы.
5. Добавь памятку «Как отмечать прогресс» (как в шаблоне) — опиши перевод`- [ ] → - [x]`с датой/итерацией и ссылкой на изменения.
6. При необходимости разверни`feature-impl`для дополнений (Wave 7 задачи).
7. Начни ответ со строки`Checkbox updated: tasklist drafted`, затем перечисли ключевые чекбоксы, которые нужно закрыть первыми.

## Fail-fast и вопросы
- Нет плана/PRD Review READY — остановись и попроси выполнить предыдущие шаги.
- Если непонятно, кто владеет action items, запроси владельцев до фиксации чеклистов.

## Ожидаемый вывод
- Актуальный`aidd/docs/tasklist/`<ticket>`.md`с фронт-маттером, чеклистами по этапам, переносом action items из PRD Review и памяткой по прогрессу.
- Ответ начинается со строки`Checkbox updated: tasklist drafted` и содержит список приоритетных чекбоксов.

## Примеры CLI
-`/tasks-new ABC-123`
-`!bash -lc 'claude-workflow preset feature-impl --ticket "ABC-123"'`
