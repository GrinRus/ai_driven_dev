---
description: "Код-ревью и возврат замечаний в задачи"
argument-hint: "<TICKET> [note...]"
lang: ru
prompt_version: 1.0.2
source_version: 1.0.2
allowed-tools:
  - Read
  - Edit
  - Write
  - Grep
  - Glob
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py:*)"
  - "Bash(claude-workflow reviewer-tests:*)"
  - "Bash(claude-workflow progress:*)"
  - "Bash(./gradlew:*)"
  - "Bash(gradle:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/review` запускает саб-агента **reviewer** для проверки изменений перед QA. Она фиксирует замечания в `aidd/docs/tasklist/<ticket>.md`, управляет маркером обязательных тестов и синхронизирует прогресс. Свободный ввод после тикета используй как доп. контекст ревью.

## Входные артефакты
- Текущий `git diff`/ PR.
- `@aidd/docs/prd/<ticket>.prd.md`, `@aidd/docs/plan/<ticket>.md`, `@aidd/docs/tasklist/<ticket>.md` — критерии приёмки и чеклисты.
- Логи тестов/гейтов (если есть),`reports/reviewer/<ticket>.json` для статуса тестов.

## Когда запускать
- После `/implement`, до `/qa`.
- Повторять до тех пор, пока все блокеры не сняты.

## Автоматические хуки и переменные
- `claude-workflow reviewer-tests --status required/optional/clear` управляет обязательностью тестов (используется format-and-test).
- `claude-workflow progress --source review --ticket <ticket>` фиксирует наличие новых `[x]` после правок tasklist.
- При необходимости запусти пресет `feature-release` для подготовки release notes.
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py review` фиксирует стадию `review`.

## Что редактируется
- Код/конфиги (для мелких фиксов) и `aidd/docs/tasklist/<ticket>.md`(замечания, закрытые чекбоксы).
- Возможное обновление `aidd/docs/release-notes.md` при подготовке релиза.

## Пошаговый план
1. Зафиксируй стадию `review`: `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py review`.
2. Вызови саб-агента **reviewer** — он проанализирует diff, сверит его с PRD/планом и сформирует список замечаний.
3. Если reviewer считает, что нужны тесты, установи `claude-workflow reviewer-tests --status required [--ticket $1]`; после зелёного прогона переведи в `optional`.
4. Обнови `aidd/docs/tasklist/<ticket>.md`: какие пункты закрыты, какие остаются `- [ ]`, ссылки на строки/файлы.
5. Запусти `!bash -lc 'claude-workflow progress --source review --ticket "$1"'`.
6. В ответе изложи статус READY/WARN/BLOCKED и список следующих шагов.

## Fail-fast и вопросы
- Нет актуального tasklist/плана — попроси пользователя их обновить.
- Если diff содержит неожиданные изменения (не по тикету) — остановись и согласуй объём.
- При невозможности запустить тесты сообщи об этом и не переводите статус READY.

## Ожидаемый вывод
- `aidd/docs/tasklist/<ticket>.md` содержит новые `- [x]`/замечания.
- Отмечено, нужен ли дополнительный прогон тестов.
- Ответ начинается со строки `Checkbox updated: ...`, затем идёт резюме состояния тикета.

## Примеры CLI
- `/review ABC-123`
- `!bash -lc 'claude-workflow reviewer-tests --status required --ticket "ABC-123"'`
