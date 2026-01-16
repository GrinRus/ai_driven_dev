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
  - "Bash(sed:*)"
  - "Bash(PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli progress:*)"
  - "Bash(PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli prd-review:*)"
  - "Bash(PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli set-active-stage:*)"
  - "Bash(PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli set-active-feature:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/review-spec` объединяет ревью плана и PRD и **последовательно запускает саб-агентов** `plan-reviewer` → `prd-reviewer`. Она подтверждает исполняемость плана, затем проводит PRD review, обновляет `## Plan Review` и `## PRD Review` и сохраняет отчёт. Свободный ввод после тикета используйте как дополнительный контекст ревью.
Следуй attention‑policy из `aidd/AGENTS.md` и начни с `aidd/docs/anchors/review-plan.md` и `aidd/docs/anchors/review-prd.md`.

## Входные артефакты
- `@aidd/docs/plan/<ticket>.md` — план реализации.
- `@aidd/docs/prd/<ticket>.prd.md` — PRD и AIDD:ACCEPTANCE.
- `@aidd/docs/research/<ticket>.md` — интеграции и reuse.
- ADR (если есть).

## Когда запускать
- После `/plan-new`, чтобы пройти review-plan и review-prd одним шагом.
- Повторять после существенных правок плана или PRD.

## Автоматические хуки и переменные
- `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli set-active-stage review-plan` фиксирует стадию `review-plan` перед проверкой плана.
- `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli set-active-stage review-prd` фиксирует стадию `review-prd` перед PRD review.
- `gate-workflow` требует `Status: READY` в `## Plan Review` и `## PRD Review` перед кодом.
- Команда `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli prd-review --ticket <ticket> --report "aidd/reports/prd/<ticket>.json" --emit-text` сохраняет отчёт PRD.
- Команда должна **запускать саб-агентов** `plan-reviewer` и `prd-reviewer` (Claude: Run agent → …).

## Что редактируется
- `aidd/docs/plan/<ticket>.md` — раздел `## Plan Review`.
- `aidd/docs/prd/<ticket>.prd.md` — раздел `## PRD Review`.
- `aidd/docs/tasklist/<ticket>.md` — перенос блокирующих action items (если есть).
- `aidd/reports/prd/<ticket>.json` — отчёт PRD review.

## Пошаговый план
1. Зафиксируй стадию `review-plan`, запусти саб-агента `plan-reviewer` и обнови `## Plan Review`.
2. Если план в статусе `BLOCKED` — остановись и верни вопросы.
3. Перед PRD review проверь консистентность PRD: `AIDD:OPEN_QUESTIONS` не содержит вопросов с ответами в `AIDD:ANSWERS`, `Status:` в шапке согласован, `AIDD:METRICS/RISKS/ROLL_OUT` синхронизированы с планом. При несоответствиях верни блокирующие вопросы и попроси обновить PRD.
4. Зафиксируй стадию `review-prd`, запусти саб-агента `prd-reviewer` и обнови `## PRD Review`.
5. Перенеси блокирующие action items в tasklist и сохрани отчёт через `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli prd-review`.

## Fail-fast и вопросы
- Нет плана/PRD/research → остановись и попроси завершить `/plan-new` или `/researcher`.
- При блокерах верни `BLOCKED` и вопросы в формате `Вопрос N (Blocker|Clarification)` с `Зачем/Варианты/Default`.
- Если ответы приходят в чате — попроси блок `AIDD:ANSWERS` с форматом `Answer N: ...` (номер совпадает с `Вопрос N`) и зафиксируй его в соответствующем артефакте (PRD/Plan).

## Ожидаемый вывод
- `## Plan Review` и `## PRD Review` обновлены и имеют статусы.
- Отчёт `aidd/reports/prd/<ticket>.json` сохранён.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/review-spec ABC-123`
