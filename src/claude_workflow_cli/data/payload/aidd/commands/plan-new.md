---
description: "План реализации по PRD + валидация"
argument-hint: "<TICKET> [note...]"
lang: ru
prompt_version: 1.1.1
source_version: 1.1.1
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(sed:*)"
  - "Bash(claude-workflow set-active-stage:*)"
  - "Bash(claude-workflow set-active-feature:*)"
  - "Bash(claude-workflow research-check:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/plan-new` строит план реализации по PRD и research, фиксирует стадию `plan`, запускает саб-агентов `planner` и `validator`. Свободный ввод после тикета используйте как уточнения для плана, включая блок `AIDD:ANSWERS` (если ответы уже есть).
Следуй attention‑policy из `aidd/AGENTS.md` и начни с `aidd/docs/anchors/plan.md`.

## Входные артефакты
- `@aidd/docs/prd/<ticket>.prd.md` — статус `READY` обязателен.
- `@aidd/docs/research/<ticket>.md` — проверяется через `claude-workflow research-check`.
- ADR (если есть) — архитектурные решения/ограничения.

## Когда запускать
- После `/idea-new` и `/researcher` (если он нужен), когда PRD готов.
- Повторный запуск — для актуализации плана при изменениях требований.

## Автоматические хуки и переменные
- `claude-workflow set-active-stage plan` фиксирует стадию `plan`.
- Команда должна запускать саб-агентов `planner` и `validator` (Claude: Run agent → planner/validator); при статусе `BLOCKED` возвращает вопросы.
- Перед запуском planner выполни `claude-workflow research-check --ticket <ticket>`.
- `gate-workflow` проверяет, что план/тасклист существуют до правок кода.

## Что редактируется
- `aidd/docs/plan/<ticket>.md` — основной результат.
- При необходимости синхронизируй открытые вопросы/риски с PRD.

## Пошаговый план
1. Зафиксируй стадию `plan`: `claude-workflow set-active-stage plan`.
2. Проверь, что PRD `Status: READY`; затем запусти `claude-workflow research-check --ticket <ticket>` и остановись при ошибке.
3. Запусти саб-агента `planner` для генерации/обновления плана; он не должен дублировать вопросы из PRD и должен использовать ссылки `PRD QN` при необходимости.
4. Если пользователь передал `AIDD:ANSWERS`, зафиксируй их в плане и закрой соответствующие вопросы (перенеси в `AIDD:DECISIONS` или пометь resolved).
5. Запусти саб-агента `validator`; при `BLOCKED` верни вопросы пользователю.
6. Убедись, что план содержит нужные секции (модули/файлы, итерации, тесты, риски).

## Fail-fast и вопросы
- Нет READY PRD или `research-check` падает — остановись и попроси завершить предыдущие шаги.
- При `BLOCKED` от validator верни вопросы в формате `Вопрос N (Blocker|Clarification)` с `Зачем/Варианты/Default`.
- Если ответы приходят в чате — попроси блок `AIDD:ANSWERS` с форматом `Answer N: ...` (номер совпадает с `Вопрос N`).
- Если вопросы уже присутствуют/закрыты в PRD — не задавай их повторно, синхронизируй через `AIDD:OPEN_QUESTIONS` и `AIDD:DECISIONS`.

## Ожидаемый вывод
- `aidd/docs/plan/<ticket>.md` обновлён и валидирован.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/plan-new ABC-123`
