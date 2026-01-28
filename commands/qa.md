---
description: "Финальная QA-проверка фичи"
argument-hint: "$1 [note...]"
lang: ru
prompt_version: 1.0.22
source_version: 1.0.22
allowed-tools:
  - Read
  - Edit
  - Glob
  - "Bash(rg:*)"
  - "Bash(npm:*)"
  - "Bash(pnpm:*)"
  - "Bash(yarn:*)"
  - "Bash(pytest:*)"
  - "Bash(python:*)"
  - "Bash(go:*)"
  - "Bash(mvn:*)"
  - "Bash(make:*)"
  - "Bash(./gradlew:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh:*)"
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
Команда `/feature-dev-aidd:qa` работает inline: фиксирует стадию и активную фичу, запускает `${CLAUDE_PLUGIN_ROOT}/tools/qa.sh --gate` для отчёта, пишет Context Pack и явно запускает саб‑агента **feature-dev-aidd:qa**. Агент обновляет QA секцию tasklist; команда формирует handoff‑задачи и фиксирует прогресс. Выполняется после `/feature-dev-aidd:review`.
Следуй attention‑policy из `aidd/AGENTS.md` и начни с `aidd/docs/anchors/qa.md`.

## Входные артефакты
- `aidd/docs/prd/$1.prd.md` (AIDD:ACCEPTANCE).
- `aidd/docs/plan/$1.md`.
- `aidd/docs/tasklist/$1.md`.
- `aidd/docs/spec/$1.spec.yaml` (если есть).
- `aidd/reports/research/$1-rlm.pack.*` (pack-first), `rlm-slice` pack (по запросу).
- Логи тестов/гейтов (если есть).

## Evidence Read Policy (RLM-first)
- Primary evidence: `aidd/reports/research/<ticket>-rlm.pack.*` (pack-first summary).
- Slice on demand: `${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh --ticket <ticket> --query "<token>"`.
- Use raw `rg` only for spot-checks.
- Legacy `ast_grep` evidence is fallback-only.

## Когда запускать
- После `/feature-dev-aidd:review`, перед релизом.
- Повторять при новых изменениях.

## Автоматические хуки и переменные
- `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh qa` фиксирует стадию `qa`.
- Команда должна запускать саб-агента **feature-dev-aidd:qa**.
- `${CLAUDE_PLUGIN_ROOT}/tools/qa.sh --ticket $1 --report "aidd/reports/qa/$1.json" --gate` формирует отчёт.
- `${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh --source qa --append --ticket $1` добавляет handoff‑задачи в `AIDD:HANDOFF_INBOX`.
- `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source qa --ticket $1` фиксирует новые `[x]`.
- При рассинхроне tasklist используй `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh --ticket $1` и, при необходимости, `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-normalize.sh --ticket $1 --fix`.

## Что редактируется
- `aidd/docs/tasklist/$1.md`.
- `aidd/reports/qa/$1.json`.

## Context Pack (шаблон)
- Шаблон: `aidd/reports/context/template.context-pack.md`.
- Целевой файл: `aidd/reports/context/$1.qa.pack.md` (stage/agent/paths/what-to-do заполняются под qa).
- Paths: plan, tasklist, prd, arch_profile, spec/research/test_policy (if exists), qa_report.
- What to do now: validate acceptance criteria, add QA traceability + handoff.
- User note: $ARGUMENTS.

## Пошаговый план
1. Команда (до subagent): зафиксируй стадию `qa` через `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh qa` и активную фичу через `${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh "$1"`.
2. Команда (до subagent): запусти `${CLAUDE_PLUGIN_ROOT}/tools/qa.sh --ticket $1 --report "aidd/reports/qa/$1.json" --gate`.
3. Команда (до subagent): собери Context Pack `aidd/reports/context/$1.qa.pack.md` по шаблону `aidd/reports/context/template.context-pack.md`; если pack не записался — верни `Status: BLOCKED`.
4. Команда → subagent: **Use the feature-dev-aidd:qa subagent. First action: Read `aidd/reports/context/$1.qa.pack.md`.**
5. Subagent: обновляет QA секцию tasklist (AIDD:CHECKLIST_QA или QA‑подсекцию `AIDD:CHECKLIST`), `AIDD:QA_TRACEABILITY`, вычисляет QA статус (front‑matter `Status` + `AIDD:CONTEXT_PACK Status`) по правилам NOT MET/NOT VERIFIED и reviewer‑tests; статус только `READY|WARN|BLOCKED`.
6. Subagent: выполняет verify results (QA evidence) и не выставляет финальный non‑BLOCKED статус без верификации (кроме `profile: none`).
7. Команда (после subagent): запусти `${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh --source qa --append --ticket $1`.
8. Команда (после subagent): подтверди прогресс через `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source qa --ticket $1`.
9. При некорректном tasklist — `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh --ticket $1` → `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-normalize.sh --ticket $1 --fix`.

## Fail-fast и вопросы
- Нет tasklist/PRD — остановись и попроси обновить артефакты.
- Отчёт не записался — перезапусти CLI команду и приложи stderr.
- Если `aidd/reports/context/$1.qa.pack.md` отсутствует после записи — верни `Status: BLOCKED`.

## Ожидаемый вывод
- Обновлённый tasklist и отчёт QA.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/feature-dev-aidd:qa ABC-123`
- `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh --ticket ABC-123`
