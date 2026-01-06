---
description: "План реализации по PRD + валидация"
argument-hint: "<TICKET> [note...]"
lang: ru
prompt_version: 1.0.8
source_version: 1.0.8
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_feature.py:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/plan-new` строит план реализации по PRD и research, фиксирует стадию `plan`, запускает саб-агентов `planner` и `validator`. Следующий шаг — `/review-spec`. Свободный ввод после тикета используйте как уточнения для плана.

## Входные артефакты
- `@aidd/docs/prd/<ticket>.prd.md` — статус `READY` обязателен.
- `@aidd/docs/research/<ticket>.md` — статус `reviewed` (или baseline по правилам гейтов).
- ADR (если есть) — архитектурные решения/ограничения.

## Когда запускать
- После `/idea-new` и `/researcher` (если он нужен), когда PRD готов.
- Повторный запуск — для актуализации плана при изменениях требований.

## Автоматические хуки и переменные
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py plan` фиксирует стадию `plan`.
- Команда должна запускать саб-агентов `planner` и `validator` (Claude: Run agent → planner/validator); при статусе `BLOCKED` возвращает вопросы.
- `gate-workflow` проверяет, что план/тасклист существуют до правок кода.

## Что редактируется
- `aidd/docs/plan/<ticket>.md` — основной результат.
- При необходимости синхронизируй открытые вопросы/риски с PRD.

## Пошаговый план
1. Зафиксируй стадию `plan`: `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py plan`.
2. Проверь, что PRD `Status: READY` и research актуален; если нет — остановись.
3. Запусти саб-агента `planner` для генерации/обновления плана.
4. Запусти саб-агента `validator`; при `BLOCKED` верни вопросы пользователю.
5. Убедись, что план содержит нужные секции (модули/файлы, итерации, тесты, риски).

## Fail-fast и вопросы
- Нет READY PRD или research — остановись и попроси завершить предыдущие шаги.
- При `BLOCKED` от validator верни вопросы в формате `Вопрос N (Blocker|Clarification)` с `Зачем/Варианты/Default`.

## Ожидаемый вывод
- `aidd/docs/plan/<ticket>.md` обновлён и валидирован.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions` (следующий шаг — `/review-spec`).

## Примеры CLI
- `/plan-new ABC-123`
