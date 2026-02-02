---
description: "Код-ревью и возврат замечаний в задачи"
argument-hint: "$1 [note...]"
lang: ru
prompt_version: 1.0.26
source_version: 1.0.26
allowed-tools:
  - Read
  - Edit
  - Glob
  - "Bash(rg:*)"
  - "Bash(sed:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/loop-pack.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/diff-boundary-check.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/review-report.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/review-pack.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/reviewer-tests.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/progress.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/stage-result.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/tasklist-normalize.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/feature-dev-aidd:review` работает inline: фиксирует стадию и активную фичу, пишет Context Pack и явно запускает саб‑агента **feature-dev-aidd:reviewer** для проверки изменений перед QA и фиксации замечаний в tasklist. Review diff‑first: проверяет только изменения итерации; исправимые дефекты → `REVISE` + handoff, loop продолжается до фикса. После ревью команда создаёт отчёт и формирует handoff‑задачи в `AIDD:HANDOFF_INBOX`. Свободный ввод после тикета используй как контекст ревью.
Следуй attention‑policy из `aidd/AGENTS.md`, канону `aidd/docs/prompting/conventions.md` и начни с `aidd/docs/anchors/review.md`.

## Входные артефакты
- Diff/PR.
- `aidd/docs/prd/$1.prd.md`, `aidd/docs/plan/$1.md`, `aidd/docs/tasklist/$1.md`.
- `aidd/docs/spec/$1.spec.yaml` (если есть).
- Логи тестов/гейтов (если есть), `aidd/reports/reviewer/$1/<scope_key>.json`.

## Evidence Read Policy (RLM-first)
- Primary evidence: `aidd/reports/research/<ticket>-rlm.pack.json` (pack-first summary).
- Slice on demand: `${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh --ticket <ticket> --query "<token>"`.
- Use raw `rg` only for spot-checks.
- Legacy `ast_grep` evidence is fallback-only.

## Когда запускать
- После `/feature-dev-aidd:implement`, до `/feature-dev-aidd:qa`.
- Повторять до снятия блокеров.

## Автоматические хуки и переменные
- `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh review` фиксирует стадию `review`.
- `${CLAUDE_PLUGIN_ROOT}/tools/loop-pack.sh --ticket $1 --stage review` создаёт loop pack и задаёт `.active_ticket`/`.active_work_item`.
- Команда должна запускать саб-агента **feature-dev-aidd:reviewer**.
- `${CLAUDE_PLUGIN_ROOT}/tools/review-report.sh --ticket $1` сохраняет отчёт ревью в `aidd/reports/reviewer/$1/<scope_key>.json`.
- `${CLAUDE_PLUGIN_ROOT}/tools/review-pack.sh --ticket $1` создаёт `review.latest.pack.md` для следующего implement (per scope_key).
- `${CLAUDE_PLUGIN_ROOT}/tools/reviewer-tests.sh --ticket $1 --status required|optional|skipped|not-required` управляет обязательностью тестов (`--clear` удаляет маркер).
- `${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh --source review --append --ticket $1` добавляет handoff‑задачи в `AIDD:HANDOFF_INBOX`.
- `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source review --ticket $1` фиксирует новые `[x]`.
- `${CLAUDE_PLUGIN_ROOT}/tools/stage-result.sh` записывает `stage_result` (обязателен для loop-step).
- При проблемах tasklist используй `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh --ticket $1` и нормализацию `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-normalize.sh --ticket $1 --fix`.

## Что редактируется
- `aidd/docs/tasklist/$1.md` (замечания, прогресс).
- `aidd/reports/reviewer/$1/<scope_key>.json`.

## Context Pack (шаблон)
- Шаблон: `aidd/reports/context/template.context-pack.md`.
- Целевой файл: `aidd/reports/context/$1.review.pack.md` (stage/agent/paths/what-to-do заполняются под review).
- Paths: plan, tasklist, prd, arch_profile, loop_pack, review_pack (if exists), spec/research/test_policy (if exists), review_report (if exists).
- What to do now: review diff vs plan/tasklist, add handoff findings.
- User note: $ARGUMENTS.

## Пошаговый план
1. Команда (до subagent): зафиксируй стадию `review` через `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh review` и активную фичу через `${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh "$1"`.
2. Команда (до subagent): создай loop pack `${CLAUDE_PLUGIN_ROOT}/tools/loop-pack.sh --ticket $1 --stage review`.
3. Команда (до subagent): собери Context Pack `aidd/reports/context/$1.review.pack.md` по шаблону `aidd/reports/context/template.context-pack.md`; если pack не записался — верни `Status: BLOCKED`.
4. Команда → subagent: **Use the feature-dev-aidd:reviewer subagent. First action: Read loop pack, затем `aidd/reports/context/$1.review.pack.md`.**
5. Subagent: обновляет tasklist (AIDD:CHECKLIST_REVIEW, handoff, front‑matter `Status/Updated`, `AIDD:CONTEXT_PACK Status`) и использует только `READY|WARN|BLOCKED` (исправимые дефекты → `WARN`/`REVISE`).
6. Subagent: выполняет verify results (review evidence) и не выставляет финальный non‑BLOCKED статус без верификации (кроме `profile: none`).
7. Команда (после subagent): проверь scope через `${CLAUDE_PLUGIN_ROOT}/tools/diff-boundary-check.sh --ticket $1` и зафиксируй результат (`OK|OUT_OF_SCOPE <path>|FORBIDDEN <path>|NO_BOUNDARIES_DEFINED`) в ответе/логах; `OUT_OF_SCOPE/NO_BOUNDARIES_DEFINED → Status: WARN` + handoff, `FORBIDDEN → Status: BLOCKED`.
8. Команда (после subagent): сохрани отчёт ревью через `${CLAUDE_PLUGIN_ROOT}/tools/review-report.sh --ticket $1`.
9. Команда (после subagent): собери review pack `${CLAUDE_PLUGIN_ROOT}/tools/review-pack.sh --ticket $1`.
10. Команда (после subagent): запиши stage result `${CLAUDE_PLUGIN_ROOT}/tools/stage-result.sh --ticket $1 --stage review --result <blocked|continue|done> --work-item-key <iteration_id=...>` (work_item_key бери из `.active_work_item`; `done` при SHIP, `continue` при REVISE; `blocked` только при missing artifacts/evidence или `FORBIDDEN`).
11. Команда (после subagent): при необходимости запроси автотесты через `${CLAUDE_PLUGIN_ROOT}/tools/reviewer-tests.sh --ticket $1 --status required|optional|skipped|not-required` (или `--clear`).
12. Команда (после subagent): запусти `${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh --source review --append --ticket $1`.
13. Команда (после subagent): подтверди прогресс через `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source review --ticket $1`.
14. Если tasklist невалиден — `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh --ticket $1` → `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-normalize.sh --ticket $1 --fix`.

## Fail-fast и вопросы
- Нет актуального tasklist/плана — остановись и попроси обновить артефакты.
- Если diff не соответствует тикету — `Status: WARN` + handoff (BLOCKED только при missing artifacts/evidence или `FORBIDDEN`).
- Если `aidd/reports/context/$1.review.pack.md` отсутствует после записи — верни `Status: BLOCKED`.
- Если `.active_mode=loop` и требуются ответы — `Status: BLOCKED` + handoff (без вопросов в чат).

## Ожидаемый вывод
- Обновлённый `aidd/docs/tasklist/$1.md`.
- Ответ содержит `Checkbox updated`, `Status`, `Work item key`, `Artifacts updated`, `Tests`, `Next actions` (output‑контракт соблюдён).

## Примеры CLI
- `/feature-dev-aidd:review ABC-123`
- `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh --ticket ABC-123`
