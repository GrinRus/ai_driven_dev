---
description: "Финальная QA-проверка фичи"
argument-hint: "$1 [note...]"
lang: ru
prompt_version: 1.0.30
source_version: 1.0.30
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
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/stage-result.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/status-summary.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/tasklist-normalize.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/feature-dev-aidd:qa` работает inline: фиксирует стадию и активную фичу, запускает `${CLAUDE_PLUGIN_ROOT}/tools/qa.sh --gate` для отчёта, пишет Context Pack и явно запускает саб‑агента **feature-dev-aidd:qa**. Агент обновляет QA секцию tasklist; команда формирует handoff‑задачи и фиксирует прогресс. Выполняется после `/feature-dev-aidd:review`.
Следуй `aidd/AGENTS.md` и канону `aidd/docs/prompting/conventions.md` (pack‑first/read‑budget).

## Входные артефакты
- `aidd/docs/prd/$1.prd.md` (AIDD:ACCEPTANCE).
- `aidd/docs/plan/$1.md`.
- `aidd/docs/tasklist/$1.md`.
- `aidd/docs/spec/$1.spec.yaml` (если есть).
- `aidd/reports/research/$1-rlm.pack.json` (pack-first), `rlm-slice` pack (по запросу).
- Логи тестов/гейтов (если есть).
- `aidd/reports/tests/$1/<scope_key>.jsonl` (ticket-scoped, если есть).

## Evidence Read Policy (RLM-first)
- Primary evidence: `aidd/reports/research/<ticket>-rlm.pack.json` (pack-first summary).
- Slice on demand: `${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh --ticket <ticket> --query "<token>"`.
- Use raw `rg` only for spot-checks.

## Когда запускать
- После `/feature-dev-aidd:review`, перед релизом.
- Повторять при новых изменениях.
- Если QA `BLOCKED` и требуется вернуться в implement/review‑loop — используйте loop‑скрипты с `--from-qa`.

## Автоматические хуки и переменные
- `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh qa` фиксирует стадию `qa`.
- Команда должна запускать саб-агента **feature-dev-aidd:qa**.
- `${CLAUDE_PLUGIN_ROOT}/tools/qa.sh --ticket $1 --report "aidd/reports/qa/$1.json" --gate` формирует отчёт.
- `${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh --source qa --append --ticket $1` добавляет handoff‑задачи в `AIDD:HANDOFF_INBOX`.
- `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source qa --ticket $1` фиксирует новые `[x]`.
- `${CLAUDE_PLUGIN_ROOT}/tools/stage-result.sh` записывает `stage_result` (ticket‑scoped).
- При рассинхроне tasklist используй `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh --ticket $1` и, при необходимости, `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-normalize.sh --ticket $1 --fix`.

## Что редактируется
- `aidd/docs/tasklist/$1.md`.
- `aidd/reports/qa/$1.json`.

## Context Pack (шаблон)
- Шаблон: `aidd/reports/context/template.context-pack.md`.
- Целевой файл: `aidd/reports/context/$1.pack.md` (rolling pack).
- Заполни поля stage/agent/read_next/artefact_links/what_to_do/user_note под qa.
- Read next: rolling context pack → QA report (если есть) → tasklist excerpt.
- What to do now: validate acceptance criteria, add QA traceability + handoff.
- User note: $ARGUMENTS.

## Пошаговый план
1. Команда (до subagent): зафиксируй стадию `qa` через `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh qa` и активную фичу через `${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh "$1"`.
2. Команда (до subagent): запусти `${CLAUDE_PLUGIN_ROOT}/tools/qa.sh --ticket $1 --report "aidd/reports/qa/$1.json" --gate`.
3. Команда (до subagent): собери Context Pack через `${CLAUDE_PLUGIN_ROOT}/tools/context-pack.sh --ticket $1 --agent qa --stage qa --read-next "aidd/reports/context/$1.pack.md" --read-next "aidd/reports/qa/$1.json" --read-next "<tasklist excerpt>" --artefact-link "<artifact: path>" --what-to-do "<qa focus>" --user-note "$ARGUMENTS"`; если pack не записался — верни `Status: BLOCKED`.
4. Команда → subagent: **Use the feature-dev-aidd:qa subagent. First action: Read `aidd/reports/context/$1.pack.md`.**
5. Subagent: обновляет QA секцию tasklist (AIDD:CHECKLIST_QA или QA‑подсекцию `AIDD:CHECKLIST`), `AIDD:QA_TRACEABILITY`, вычисляет QA статус (front‑matter `Status` + `AIDD:CONTEXT_PACK Status`) по правилам NOT MET/NOT VERIFIED и reviewer‑tests; статус только `READY|WARN|BLOCKED` (`tests_required=soft` + missing/skip → `WARN`, `tests_required=hard` → `BLOCKED`).
6. Subagent: выполняет verify results (QA evidence) и не выставляет финальный non‑BLOCKED статус без верификации (кроме `profile: none`).
7. Команда (после subagent): запусти `${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh --source qa --append --ticket $1`.
8. Команда (после subagent): подтверди прогресс через `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source qa --ticket $1`.
9. Команда (после subagent): запиши stage result `${CLAUDE_PLUGIN_ROOT}/tools/stage-result.sh --ticket $1 --stage qa --result <blocked|done>` (READY/WARN → `done`; BLOCKED только при missing artifacts/evidence или `tests_required=hard`). QA stage_result ticket‑scoped (`scope_key=<ticket>`); при раннем `BLOCKED` используй `--allow-missing-work-item`.
10. Команда (после subagent): сформируй финальный статус через `${CLAUDE_PLUGIN_ROOT}/tools/status-summary.sh --ticket $1 --stage qa` и используй его в ответе (single source of truth).
11. При некорректном tasklist — `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh --ticket $1` → `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-normalize.sh --ticket $1 --fix`.

## Fail-fast и вопросы
- Нет tasklist/PRD — остановись и попроси обновить артефакты.
- Отчёт не записался — перезапусти CLI команду и приложи stderr.
- Если `aidd/reports/context/$1.pack.md` отсутствует после записи — верни `Status: BLOCKED`.
- Если `.active_mode=loop` и требуются ответы — `Status: BLOCKED` + handoff (без вопросов в чат).
- Любой ранний `BLOCKED` фиксируй через `${CLAUDE_PLUGIN_ROOT}/tools/stage-result.sh` (при необходимости `--allow-missing-work-item`).
- Любой ранний `BLOCKED` (до subagent) всё равно выводит полный контракт: `Status/Work item key/Artifacts updated/Tests/Blockers/Handoff/Next actions`; если данных нет — `n/a`. `Tests: run` запрещён без tests_log → используй `Tests: skipped` + reason_code.

## Ожидаемый вывод
- Обновлённый tasklist и отчёт QA.
- `Status: READY|WARN|BLOCKED`.
- `Work item key: <ticket>` (или `n/a` при раннем BLOCKED).
- `Artifacts updated: <paths>`.
- `Tests: run|skipped|not-required <profile/summary/evidence>` (без tests_log → `skipped` + reason_code).
- `Blockers/Handoff: ...`.
- `Next actions: ...`.
- `AIDD:READ_LOG: <paths>`.
- Финальный `Status` должен совпадать с выводом `${CLAUDE_PLUGIN_ROOT}/tools/status-summary.sh`.
- Итоговый Status в ответе: приоритет `stage_result` → `qa report` → `pack`. При расхождении выбери безопасный статус (BLOCKED > WARN > READY) и укажи `reason_code=sync_drift_warn`.
- Ответ содержит `Checkbox updated` (если есть).

## Примеры CLI
- `/feature-dev-aidd:qa ABC-123`
- `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh --ticket ABC-123`
