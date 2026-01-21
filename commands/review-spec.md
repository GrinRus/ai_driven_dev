---
description: "Совместное ревью плана и PRD (review-plan + review-prd)"
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
  - "Bash(sed:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/progress.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/prd-review.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/feature-dev-aidd:review-spec` объединяет ревью плана и PRD и **последовательно запускает саб-агентов** `feature-dev-aidd:plan-reviewer` → `feature-dev-aidd:prd-reviewer`. Она подтверждает исполняемость плана, затем проводит PRD review, обновляет `## Plan Review` и `## PRD Review` и сохраняет отчёт. Свободный ввод после тикета используйте как дополнительный контекст ревью.
Следуй attention‑policy из `aidd/AGENTS.md` и начни с `aidd/docs/anchors/review-plan.md` и `aidd/docs/anchors/review-prd.md`.

## Входные артефакты
- `@aidd/docs/plan/<ticket>.md` — план реализации.
- `@aidd/docs/prd/<ticket>.prd.md` — PRD и AIDD:ACCEPTANCE.
- `@aidd/docs/research/<ticket>.md` — интеграции и reuse.
- ADR (если есть).

## Когда запускать
- После `/feature-dev-aidd:plan-new`, чтобы пройти review-plan и review-prd одним шагом.
- Повторять после существенных правок плана или PRD.

## Автоматические хуки и переменные
- `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh review-plan` фиксирует стадию `review-plan` перед проверкой плана.
- `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh review-prd` фиксирует стадию `review-prd` перед PRD review.
- `gate-workflow` требует `Status: READY` в `## Plan Review` и `## PRD Review` перед кодом.
- Команда `${CLAUDE_PLUGIN_ROOT}/tools/prd-review.sh --ticket <ticket> --report "aidd/reports/prd/<ticket>.json" --emit-text` сохраняет отчёт PRD.
- Команда должна **запускать саб-агентов** `feature-dev-aidd:plan-reviewer` и `feature-dev-aidd:prd-reviewer` (Claude: Run agent → feature-dev-aidd:plan-reviewer/feature-dev-aidd:prd-reviewer).

## Что редактируется
- `aidd/docs/plan/<ticket>.md` — раздел `## Plan Review`.
- `aidd/docs/prd/<ticket>.prd.md` — раздел `## PRD Review`.
- `aidd/docs/tasklist/<ticket>.md` — перенос блокирующих action items (если есть).
- `aidd/reports/prd/<ticket>.json` — отчёт PRD review.

## Пошаговый план
1. Зафиксируй стадию `review-plan`, запусти саб-агента `feature-dev-aidd:plan-reviewer` и обнови `## Plan Review`.
2. Если план в статусе `BLOCKED` — остановись и верни вопросы.
3. Перед PRD review проверь консистентность PRD: `AIDD:OPEN_QUESTIONS` не содержит вопросов с ответами в `AIDD:ANSWERS`, `Status:` в шапке согласован, `AIDD:METRICS/RISKS/ROLL_OUT` синхронизированы с планом. При несоответствиях верни блокирующие вопросы и попроси обновить PRD.
4. Зафиксируй стадию `review-prd`, запусти саб-агента `feature-dev-aidd:prd-reviewer` и обнови `## PRD Review`.
5. Перенеси блокирующие action items в tasklist и сохрани отчёт через `${CLAUDE_PLUGIN_ROOT}/tools/prd-review.sh`.

## Fail-fast и вопросы
- Нет плана/PRD/research → остановись и попроси завершить `/feature-dev-aidd:plan-new` или `/feature-dev-aidd:researcher`.
- При блокерах верни `BLOCKED` и вопросы в формате `Вопрос N (Blocker|Clarification)` с `Зачем/Варианты/Default`.
- Если ответы приходят в чате — попроси блок `AIDD:ANSWERS` с форматом `Answer N: ...` (номер совпадает с `Вопрос N`) и зафиксируй его в соответствующем артефакте (PRD/Plan).

## Ожидаемый вывод
- `## Plan Review` и `## PRD Review` обновлены и имеют статусы.
- Отчёт `aidd/reports/prd/<ticket>.json` сохранён.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/feature-dev-aidd:review-spec ABC-123`
