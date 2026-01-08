---
description: "Совместное ревью плана и PRD (review-plan + review-prd)"
argument-hint: "<TICKET> [note...]"
lang: ru
prompt_version: 1.0.7
source_version: 1.0.7
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(claude-workflow progress:*)"
  - "Bash(claude-workflow prd-review:*)"
  - "Bash(claude-workflow set-active-stage:*)"
  - "Bash(claude-workflow set-active-feature:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/review-spec` объединяет ревью плана и PRD и **последовательно запускает саб-агентов** `plan-reviewer` → `prd-reviewer`. Она подтверждает исполняемость плана, затем проводит PRD review, обновляет `## Plan Review` и `## PRD Review` и сохраняет отчёт. Свободный ввод после тикета используйте как дополнительный контекст ревью.
Следуй attention‑policy из `aidd/AGENTS.md` и начни с `aidd/docs/anchors/review-plan.md` и `aidd/docs/anchors/review-prd.md`.

## Входные артефакты
- `@aidd/docs/plan/<ticket>.md` — план реализации.
- `@aidd/docs/prd/<ticket>.prd.md` — PRD и acceptance criteria.
- `@aidd/docs/research/<ticket>.md` — интеграции и reuse.
- ADR (если есть).

## Когда запускать
- После `/plan-new`, чтобы пройти review-plan и review-prd одним шагом.
- Повторять после существенных правок плана или PRD.

## Автоматические хуки и переменные
- `claude-workflow set-active-stage review-plan` фиксирует стадию `review-plan` перед проверкой плана.
- `claude-workflow set-active-stage review-prd` фиксирует стадию `review-prd` перед PRD review.
- `gate-workflow` требует `Status: READY` в `## Plan Review` и `## PRD Review` перед кодом.
- Команда `claude-workflow prd-review --ticket <ticket> --report "aidd/reports/prd/<ticket>.json" --emit-text` сохраняет отчёт PRD.
- Команда должна **запускать саб-агентов** `plan-reviewer` и `prd-reviewer` (Claude: Run agent → …).

## Что редактируется
- `aidd/docs/plan/<ticket>.md` — раздел `## Plan Review`.
- `aidd/docs/prd/<ticket>.prd.md` — раздел `## PRD Review`.
- `aidd/docs/tasklist/<ticket>.md` — перенос блокирующих action items (если есть).
- `aidd/reports/prd/<ticket>.json` — отчёт PRD review.

## Пошаговый план
1. Зафиксируй стадию `review-plan`, запусти саб-агента `plan-reviewer` и обнови `## Plan Review`.
2. Если план в статусе `BLOCKED` — остановись и верни вопросы.
3. Зафиксируй стадию `review-prd`, запусти саб-агента `prd-reviewer` и обнови `## PRD Review`.
4. Перенеси блокирующие action items в tasklist и сохрани отчёт через `claude-workflow prd-review`.

## Fail-fast и вопросы
- Нет плана/PRD/research → остановись и попроси завершить `/plan-new` или `/researcher`.
- При блокерах верни `BLOCKED` и вопросы в формате `Вопрос N (Blocker|Clarification)` с `Зачем/Варианты/Default`.

## Ожидаемый вывод
- `## Plan Review` и `## PRD Review` обновлены и имеют статусы.
- Отчёт `aidd/reports/prd/<ticket>.json` сохранён.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/review-spec ABC-123`
