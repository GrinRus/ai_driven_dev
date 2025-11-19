---
description: "Управление маркером тестов reviewer"
argument-hint: "[ticket]"
lang: ru
prompt_version: 1.0.0
source_version: 1.0.0
allowed-tools: Bash(claude-workflow reviewer-tests:*)
model: inherit
---

## Контекст
Команда управляет маркером обязательных тестов (`reports/reviewer/<ticket>.json`), который читает `.claude/hooks/format-and-test.sh`. Используется во время `/review` и `/implement`.

## Входные артефакты
- `reports/reviewer/<ticket>.json` — создаётся автоматически при первом вызове.
- Активный ticket (`docs/.active_ticket`) или переданный аргумент.

## Когда запускать
- Перед ревью, если нужно заставить format-and-test гонять полный набор задач.
- После зелёного прогона, чтобы снять обязательность.
- Для очистки статуса (например, при закрытии тикета).

## Автоматические хуки и переменные
- `claude-workflow reviewer-tests --status required|optional|not-required` управляет полем `tests` в `reports/reviewer/<ticket>.json`.
- `--clear` удаляет файл/маркер.

## Что редактируется
- Только JSON-файл `reports/reviewer/<ticket>.json` (через CLI).

## Пошаговый план
1. Требуются тесты? Выполни `claude-workflow reviewer-tests --status required [--ticket $1]`.
2. После успешного прогона установи `optional` или `not-required`: `claude-workflow reviewer-tests --status optional [--ticket $1]`.
3. Для сброса статуса или очистки артефакта выполни `claude-workflow reviewer-tests --clear [--ticket $1]`.

## Fail-fast и вопросы
- Если ticket не указан и нет активного тикета — попроси пользователя задать `--ticket`.
- Убедись, что команда понимает последствия: при статусе `required` format-and-test падает при красных тестах.

## Ожидаемый вывод
- Обновлённый статус маркера тестов и короткое описание, почему он изменён.

## Примеры CLI
- `/reviewer ABC-123 --status required` (через палитру)
- `!bash -lc 'claude-workflow reviewer-tests --status optional --ticket "ABC-123"'`
