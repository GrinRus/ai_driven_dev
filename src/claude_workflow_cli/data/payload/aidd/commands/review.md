---
description: "Код-ревью и возврат замечаний в задачи"
argument-hint: "<TICKET>"
lang: ru
prompt_version: 1.0.0
source_version: 1.0.0
allowed-tools:
  - Read
  - Edit
  - Write
  - Grep
  - Glob
  - "Bash(claude-workflow reviewer-tests:*)"
  - "Bash(claude-workflow progress:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда`/review`запускает саб-агента **reviewer** для проверки изменений перед QA. Она фиксирует замечания в`aidd/docs/tasklist/`&lt;ticket&gt;`.md`, управляет маркером обязательных тестов и синхронизирует прогресс.

## Входные артефакты
- Текущий`git diff`/ PR.
- @aidd/docs/prd/`&lt;ticket&gt;`.prd.md, @aidd/docs/plan/`&lt;ticket&gt;`.md, @aidd/docs/tasklist/`&lt;ticket&gt;`.md — критерии приёмки и чеклисты.
- Логи тестов/гейтов (если есть),`reports/reviewer/`&lt;ticket&gt;`.json`для статуса тестов.

## Когда запускать
- После`/implement`, до`/qa`.
- Повторять до тех пор, пока все блокеры не сняты.

## Автоматические хуки и переменные
-`claude-workflow reviewer-tests --status required/optional/clear`управляет обязательностью тестов (используется format-and-test).
-`claude-workflow progress --source review --ticket`&lt;ticket&gt;``фиксирует наличие новых`[x]`после правок tasklist.
- При необходимости запусти пресет`feature-release`для подготовки release notes.

## Что редактируется
- Код/конфиги (для мелких фиксов) и`aidd/docs/tasklist/`&lt;ticket&gt;`.md`(замечания, закрытые чекбоксы).
- Возможное обновление`aidd/docs/release-notes.md`при подготовке релиза.

## Пошаговый план
1. Вызови саб-агента **reviewer** — он проанализирует diff, сверит его с PRD/планом и сформирует список замечаний.
2. Если reviewer считает, что нужны тесты, установи`claude-workflow reviewer-tests --status required [--ticket $1]`; после зелёного прогона переведи в`optional`.
3. Обнови`aidd/docs/tasklist/`&lt;ticket&gt;`.md`: какие пункты закрыты, какие остаются`- [ ]`, ссылки на строки/файлы.
4. Запусти`!bash -lc 'claude-workflow progress --source review --ticket "$1"'`.
5. В ответе изложи статус READY/WARN/BLOCKED и список следующих шагов.

## Fail-fast и вопросы
- Нет актуального tasklist/плана — попроси пользователя их обновить.
- Если diff содержит неожиданные изменения (не по тикету) — остановись и согласуй объём.
- При невозможности запустить тесты сообщи об этом и не переводите статус READY.

## Ожидаемый вывод
-`aidd/docs/tasklist/`&lt;ticket&gt;`.md`содержит новые`- [x]`/замечания.
- Отмечено, нужен ли дополнительный прогон тестов.
- Ответ заканчивается`Checkbox updated: ...`и резюме состояния тикета.

## Примеры CLI
-`/review ABC-123`
-`!bash -lc 'claude-workflow reviewer-tests --status required --ticket "ABC-123"'`
