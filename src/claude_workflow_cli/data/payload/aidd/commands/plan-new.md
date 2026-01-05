---
description: "План реализации по PRD + валидация"
argument-hint: "<TICKET> [note...]"
lang: ru
prompt_version: 1.1.0
source_version: 1.1.0
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_feature.py:*)"
  - "Bash(claude-workflow research-check:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/plan-new` строит план реализации по PRD и research, фиксирует стадию `plan`, запускает саб-агентов `planner` и `validator`. Следующий шаг — `/review-spec`. Свободный ввод после тикета используйте как уточнения для плана.

## Входные артефакты
- `@aidd/docs/prd/<ticket>.prd.md` — статус `READY` обязателен.
- `@aidd/docs/research/<ticket>.md` — проверяется через `claude-workflow research-check`.
- ADR (если есть) — архитектурные решения/ограничения.

## Когда запускать
- После `/idea-new` и `/researcher` (если он нужен), когда PRD готов.
- Повторный запуск — для актуализации плана при изменениях требований.

## Автоматические хуки и переменные
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py plan` фиксирует стадию `plan`.
- Команда должна запускать саб-агентов `planner` и `validator` (Claude: Run agent → planner/validator); при статусе `BLOCKED` возвращает вопросы.
- Перед запуском planner выполни `claude-workflow research-check --ticket <ticket>`.
- `gate-workflow` проверяет, что план/тасклист существуют до правок кода.

## Что редактируется
- `aidd/docs/plan/<ticket>.md` — основной результат.
- При необходимости синхронизируй открытые вопросы/риски с PRD.

## Пошаговый план
1. Зафиксируй стадию `plan`: `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py plan`.
2. Проверь, что PRD `Status: READY`; затем запусти `claude-workflow research-check --ticket <ticket>` и остановись при ошибке.
3. Запусти саб-агента `planner` для генерации/обновления плана.
4. Запусти саб-агента `validator`; при `BLOCKED` верни вопросы пользователю.
5. Убедись, что план содержит нужные секции (модули/файлы, итерации, тесты, риски).

## Fail-fast и вопросы
- Нет READY PRD или `research-check` падает — остановись и попроси завершить предыдущие шаги.
- При `BLOCKED` от validator верни вопросы в формате `Вопрос N (Blocker|Clarification)` с `Зачем/Варианты/Default`.

## Ожидаемый вывод
- `aidd/docs/plan/<ticket>.md` обновлён и валидирован.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions` (следующий шаг — `/review-spec`).

## Примеры CLI
- `/plan-new ABC-123`
