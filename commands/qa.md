---
description: "Финальная QA-проверка фичи"
argument-hint: "$1 [note...]"
lang: ru
prompt_version: 1.0.16
source_version: 1.0.16
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/qa.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/progress.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/tasklist-normalize.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/feature-dev-aidd:qa` работает inline: фиксирует стадию и активную фичу, запускает `${CLAUDE_PLUGIN_ROOT}/tools/qa.sh --gate` для отчёта, пишет Context Pack и явно запускает саб‑агента **agent-feature-dev-aidd:qa**. Агент обновляет QA секцию tasklist; команда формирует handoff‑задачи и фиксирует прогресс. Выполняется после `/feature-dev-aidd:review`.
Следуй attention‑policy из `aidd/AGENTS.md` и начни с `aidd/docs/anchors/qa.md`.

## Входные артефакты
- `aidd/docs/prd/$1.prd.md` (AIDD:ACCEPTANCE).
- `aidd/docs/plan/$1.md`.
- `aidd/docs/tasklist/$1.md`.
- `aidd/docs/spec/$1.spec.yaml` (если есть).
- Логи тестов/гейтов (если есть).

## Когда запускать
- После `/feature-dev-aidd:review`, перед релизом.
- Повторять при новых изменениях.

## Автоматические хуки и переменные
- `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh qa` фиксирует стадию `qa`.
- Команда должна запускать саб-агента **agent-feature-dev-aidd:qa**.
- `${CLAUDE_PLUGIN_ROOT}/tools/qa.sh --ticket $1 --report "aidd/reports/qa/$1.json" --gate` формирует отчёт.
- `${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh --source qa --append --ticket $1` добавляет handoff‑задачи в `AIDD:HANDOFF_INBOX`.
- `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source qa --ticket $1` фиксирует новые `[x]`.
- При рассинхроне tasklist используй `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh --ticket $1` и, при необходимости, `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-normalize.sh --ticket $1 --fix`.

## Что редактируется
- `aidd/docs/tasklist/$1.md`.
- `aidd/reports/qa/$1.json`.

## Context Pack (шаблон)
Файл: `aidd/reports/context/$1.qa.pack.md`.

```md
# AIDD Context Pack — qa
ticket: $1
stage: qa
agent: agent-feature-dev-aidd:qa
generated_at: <UTC ISO-8601>

## Paths
- plan: aidd/docs/plan/$1.md
- tasklist: aidd/docs/tasklist/$1.md
- prd: aidd/docs/prd/$1.prd.md
- spec: aidd/docs/spec/$1.spec.yaml (if exists)
- research: aidd/docs/research/$1.md (if exists)
- test_policy: aidd/.cache/test-policy.env (if exists)
- qa_report: aidd/reports/qa/$1.json

## What to do now
- Validate acceptance criteria, add QA traceability + handoff.

## User note
- $ARGUMENTS

## Git snapshot (optional)
- branch: <git rev-parse --abbrev-ref HEAD>
- diffstat: <git diff --stat>
```

## Пошаговый план
1. Команда (до subagent): зафиксируй стадию `qa` через `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh qa` и активную фичу через `${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh "$1"`.
2. Команда (до subagent): запусти `${CLAUDE_PLUGIN_ROOT}/tools/qa.sh --ticket $1 --report "aidd/reports/qa/$1.json" --gate`.
3. Команда (до subagent): собери Context Pack `aidd/reports/context/$1.qa.pack.md` по шаблону W79-10.
4. Команда → subagent: **Use the agent-feature-dev-aidd:qa subagent. First action: Read `aidd/reports/context/$1.qa.pack.md`.**
5. Subagent: обновляет QA секцию tasklist (AIDD:CHECKLIST_QA или QA‑подсекцию `AIDD:CHECKLIST`), `AIDD:QA_TRACEABILITY`, вычисляет QA статус (front‑matter `Status` + `AIDD:CONTEXT_PACK Status`) по правилам NOT MET/NOT VERIFIED и reviewer‑tests.
6. Команда (после subagent): запусти `${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh --source qa --append --ticket $1`.
7. Команда (после subagent): подтверди прогресс через `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source qa --ticket $1`.
8. При некорректном tasklist — `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh --ticket $1` → `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-normalize.sh --ticket $1 --fix`.

## Fail-fast и вопросы
- Нет tasklist/PRD — остановись и попроси обновить артефакты.
- Отчёт не записался — перезапусти CLI команду и приложи stderr.

## Ожидаемый вывод
- Обновлённый tasklist и отчёт QA.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/feature-dev-aidd:qa ABC-123`
- `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh --ticket ABC-123`
