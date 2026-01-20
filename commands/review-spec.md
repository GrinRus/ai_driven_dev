---
description: "Совместное ревью плана и PRD (review-plan + review-prd)"
argument-hint: "$1 [note...]"
lang: ru
prompt_version: 1.0.10
source_version: 1.0.10
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
Команда `/feature-dev-aidd:review-spec` работает inline (без `context: fork`), потому что саб‑агенты не могут порождать других саб‑агентов, и **последовательно запускает саб‑агентов** `agent-feature-dev-aidd:plan-reviewer` → `agent-feature-dev-aidd:prd-reviewer`. Она подтверждает исполняемость плана, затем проводит PRD review, обновляет `## Plan Review` и `## PRD Review` и сохраняет отчёт. Свободный ввод после тикета используйте как дополнительный контекст ревью.
Следуй attention‑policy из `aidd/AGENTS.md` и начни с `aidd/docs/anchors/review-plan.md` и `aidd/docs/anchors/review-prd.md`.

## Входные артефакты
- `aidd/docs/plan/$1.md` — план реализации.
- `aidd/docs/prd/$1.prd.md` — PRD и AIDD:ACCEPTANCE.
- `aidd/docs/research/$1.md` — интеграции и reuse.
- ADR (если есть).

## Когда запускать
- После `/feature-dev-aidd:plan-new`, чтобы пройти review-plan и review-prd одним шагом.
- Повторять после существенных правок плана или PRD.

## Автоматические хуки и переменные
- `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh review-plan` фиксирует стадию `review-plan` перед проверкой плана.
- `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh review-prd` фиксирует стадию `review-prd` перед PRD review.
- `gate-workflow` требует `Status: READY` в `## Plan Review` и `## PRD Review` перед кодом.
- Команда `${CLAUDE_PLUGIN_ROOT}/tools/prd-review.sh --ticket $1 --report "aidd/reports/prd/$1.json" --emit-text` сохраняет отчёт PRD.
- Команда должна **запускать саб-агентов** `agent-feature-dev-aidd:plan-reviewer` и `agent-feature-dev-aidd:prd-reviewer`.

## Что редактируется
- `aidd/docs/plan/$1.md` — раздел `## Plan Review`.
- `aidd/docs/prd/$1.prd.md` — раздел `## PRD Review`.
- `aidd/docs/tasklist/$1.md` — перенос блокирующих action items (если есть).
- `aidd/reports/prd/$1.json` — отчёт PRD review.

## Context Pack (шаблон)
Файлы:
- `aidd/reports/context/$1.review-plan.pack.md`
- `aidd/reports/context/$1.review-prd.pack.md`

```md
# AIDD Context Pack — review-spec/<agent>
ticket: $1
stage: review-plan | review-prd
agent: agent-feature-dev-aidd:<plan-reviewer|prd-reviewer>
generated_at: <UTC ISO-8601>

## Paths
- plan: aidd/docs/plan/$1.md
- prd: aidd/docs/prd/$1.prd.md
- research: aidd/docs/research/$1.md
- tasklist: aidd/docs/tasklist/$1.md (if exists)
- spec: aidd/docs/spec/$1.spec.yaml (if exists)
- test_policy: aidd/.cache/test-policy.env (if exists)

## What to do now
- plan-reviewer: validate plan executability; prd-reviewer: validate PRD completeness.

## User note
- $ARGUMENTS

## Git snapshot (optional)
- branch: <git rev-parse --abbrev-ref HEAD>
- diffstat: <git diff --stat>
```

## Пошаговый план
1. Команда (до subagent): зафиксируй стадию `review-plan` через `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh review-plan` и активную фичу через `${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh "$1"`.
2. Команда (до subagent): собери Context Pack `aidd/reports/context/$1.review-plan.pack.md` по шаблону W79-10.
3. Команда → subagent: **Use the agent-feature-dev-aidd:plan-reviewer subagent. First action: Read `aidd/reports/context/$1.review-plan.pack.md`.**
4. Subagent (plan-reviewer): обновляет `## Plan Review`. Если `BLOCKED` — остановись и верни вопросы.
5. Команда (до subagent prd): проверь консистентность PRD (`AIDD:OPEN_QUESTIONS` vs `AIDD:ANSWERS`, статус, метрики/риски).
6. Команда (до subagent prd): зафиксируй стадию `review-prd` через `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh review-prd`.
7. Команда (до subagent prd): собери Context Pack `aidd/reports/context/$1.review-prd.pack.md` по шаблону W79-10.
8. Команда → subagent: **Use the agent-feature-dev-aidd:prd-reviewer subagent. First action: Read `aidd/reports/context/$1.review-prd.pack.md`.**
9. Subagent (prd-reviewer): обновляет `## PRD Review`.
10. Команда (после subagent): перенеси блокирующие action items в tasklist и сохрани отчёт через `${CLAUDE_PLUGIN_ROOT}/tools/prd-review.sh --ticket $1 --report "aidd/reports/prd/$1.json" --emit-text`.

## Fail-fast и вопросы
- Нет плана/PRD/research → остановись и попроси завершить `/feature-dev-aidd:plan-new` или `/feature-dev-aidd:researcher`.
- При блокерах верни `BLOCKED` и вопросы в формате `Вопрос N (Blocker|Clarification)` с `Зачем/Варианты/Default`.
- Если ответы приходят в чате — попроси блок `AIDD:ANSWERS` с форматом `Answer N: ...` (номер совпадает с `Вопрос N`) и зафиксируй его в соответствующем артефакте (PRD/Plan).

## Ожидаемый вывод
- `## Plan Review` и `## PRD Review` обновлены и имеют статусы.
- Отчёт `aidd/reports/prd/$1.json` сохранён.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/feature-dev-aidd:review-spec ABC-123`
