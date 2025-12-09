---
description: "Реализация фичи по плану + выборочные тесты"
argument-hint: "<TICKET>"
lang: ru
prompt_version: 1.1.1
source_version: 1.1.1
allowed-tools:
  - Read
  - Edit
  - Write
  - Grep
  - Glob
  - "Bash(${CLAUDE_PROJECT_DIR}/.claude/hooks/format-and-test.sh:*)"
  - "Bash(claude-workflow progress:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда`/implement`запускает саб-агента **implementer**, который работает по @aidd/docs/plan/`&lt;ticket&gt;`.md и @aidd/docs/tasklist/`&lt;ticket&gt;`.md, при необходимости сверяется с PRD/research для уточнений, обновляет tasklist и следит за запуском`${CLAUDE_PROJECT_DIR}/.claude/hooks/format-and-test.sh`перед итоговым ответом. Используется в основной разработке.

## Входные артефакты
- @aidd/docs/plan/`&lt;ticket&gt;`.md — итерации и DoD.
- @aidd/docs/tasklist/`&lt;ticket&gt;`.md — чеклист прогресса.
- @aidd/docs/research/`&lt;ticket&gt;`.md, @aidd/docs/prd/`&lt;ticket&gt;`.prd.md — доп. контекст и ограничения (используются, если не хватает деталей в плане/чеклисте).

## Когда запускать
- После`/tasks-new`, когда план и tasklist готовы.
- Повторять на каждой итерации разработки до завершения тикета.

## Автоматические хуки и переменные
-`${CLAUDE_PROJECT_DIR}/.claude/hooks/format-and-test.sh`запускается после каждой записи; управляй`SKIP_AUTO_TESTS`,`FORMAT_ONLY`,`TEST_SCOPE`,`STRICT_TESTS`при необходимости и фиксируй изменения.
-`claude-workflow progress --source implement --ticket`&lt;ticket&gt;``должен срабатывать перед завершением команды.

## Что редактируется
- Код/конфиги (`src/**`,`config/**`), а также связанные документы (plan/tasklist) согласно плану.
-`aidd/docs/tasklist/`&lt;ticket&gt;`.md`— отмечаются закрытые чекбоксы, дата, итерация, ссылка на изменения.

## Пошаговый план
1. Вызови саб-агента **implementer**: он сверится с планом/тасклистом и выполнит следующий шаг.
2. После каждой правки наблюдай за автозапуском`${CLAUDE_PROJECT_DIR}/.claude/hooks/format-and-test.sh`; при необходимости вручную запусти`!"$CLAUDE_PROJECT_DIR"/.claude/hooks/format-and-test.sh`.
3. Обнови`aidd/docs/tasklist/`&lt;ticket&gt;`.md`: переведи соответствующие чекбоксы`- [ ] → - [x]`, добавь дату/итерацию/результат.
4. Если нужна избирательность тестов, настрой`TEST_SCOPE`,`TEST_CHANGED_ONLY`, либо временно установи`SKIP_AUTO_TESTS=1`(обязательно задокументируй).
5. Перед завершением итерации выполни`!bash -lc 'claude-workflow progress --source implement --ticket "$1"'`. Если команда сообщает об отсутствии новых`[x]`, вернись к tasklist и зафиксируй прогресс.
6. В ответе перечисли, какие чекбоксы закрыты/остались, статус тестов и дальнейшие шаги.

## Fail-fast и вопросы
- Нет актуального плана/tasklist — остановись и попроси запустить`/plan-new`/`/tasks-new`.
- Неясные требования (алгоритм, интеграция, БД) — задай вопросы до продолжения.
- Падающие тесты — не продвигайся, пока не исправишь или не согласуешь временный skip.

## Ожидаемый вывод
- Обновлённый код/документы согласно плану.
-`aidd/docs/tasklist/`&lt;ticket&gt;`.md`содержит новые`- [x]`с комментариями.
- Строка`Checkbox updated: ...`отражает закрытые пункты; указаны текущие и следующие шаги.

## Примеры CLI
-`/implement ABC-123`
-`!bash -lc 'SKIP_AUTO_TESTS=1 "$CLAUDE_PROJECT_DIR"/.claude/hooks/format-and-test.sh'`
