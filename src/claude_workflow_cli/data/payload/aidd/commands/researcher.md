---
description: "Подготовка отчёта Researcher: сбор контекста и запуск агента"
argument-hint: "<TICKET> [note...] [--paths path1,path2] [--keywords kw1,kw2] [--note text]"
lang: ru
prompt_version: 1.2.2
source_version: 1.2.2
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(sed:*)"
  - "Bash(claude-workflow set-active-feature:*)"
  - "Bash(claude-workflow set-active-stage:*)"
  - "Bash(claude-workflow research:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/researcher` собирает кодовый контекст: читает `## AIDD:RESEARCH_HINTS` из PRD, запускает `claude-workflow research`, затем запускает саб-агента `researcher`, который обновляет `aidd/docs/research/<ticket>.md`. Свободный ввод после тикета используй как заметку в отчёте.
Следуй attention‑policy из `aidd/AGENTS.md` и начни с `aidd/docs/anchors/research.md`.

## Входные артефакты
- `aidd/docs/.active_ticket`, `aidd/docs/.active_feature`.
- `@aidd/docs/prd/<ticket>.prd.md` (раздел `## AIDD:RESEARCH_HINTS`).
- `@aidd/docs/research/template.md` — шаблон.
- `aidd/reports/research/<ticket>-context.json` — формируется CLI.

## Когда запускать
- После `/idea-new`, до `/plan-new`.
- Повторно — при изменениях модулей/рисков.

## Автоматические хуки и переменные
- `claude-workflow set-active-stage research` фиксирует стадию `research`.
- `claude-workflow research --ticket <ticket> --auto --deep-code --call-graph [--paths ... --keywords ... --note ...]` обновляет JSON контекст.
- Команда должна запускать саб-агента `researcher` (Claude: Run agent → researcher).
- При необходимости добавь handoff через `claude-workflow tasks-derive --source research --append --ticket <ticket>`.

## Что редактируется
- `aidd/docs/research/<ticket>.md`.
- PRD/tasklist — ссылки на отчёт.

## Пошаговый план
1. Убедись, что активный ticket задан; при необходимости вызови `claude-workflow set-active-feature`.
2. Зафиксируй стадию `research`.
3. Извлеки `## AIDD:RESEARCH_HINTS` и запусти `claude-workflow research ...` с `--paths/--keywords/--note`.
4. Запусти саб-агента `researcher` и обнови `aidd/docs/research/<ticket>.md`.
5. При необходимости добавь handoff-задачи в tasklist.

## Fail-fast и вопросы
- Нет активного тикета или PRD — остановись и попроси `/idea-new`.
- Если отчёт остаётся `pending`, верни вопросы/условия для `reviewed`.

## Ожидаемый вывод
- Обновлённый `aidd/docs/research/<ticket>.md` (status `pending|reviewed`).
- Актуальный `aidd/reports/research/<ticket>-context.json`.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/researcher ABC-123 --paths src/app:src/shared --keywords "payment,checkout" --deep-code`
