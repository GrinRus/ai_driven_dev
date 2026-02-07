---
description: "Код-ревью и возврат замечаний в задачи"
argument-hint: "$1 [note...]"
lang: ru
prompt_version: 1.0.33
source_version: 1.0.33
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
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/context-pack.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/stage-result.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/status-summary.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/tasklist-normalize.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/feature-dev-aidd:review` работает inline: фиксирует стадию и активную фичу, пишет Context Pack и явно запускает саб‑агента **feature-dev-aidd:reviewer** для проверки изменений перед QA и фиксации замечаний в tasklist. Review diff‑first: проверяет только изменения итерации; исправимые дефекты → `REVISE` + handoff, loop продолжается до фикса. После ревью команда создаёт отчёт и формирует handoff‑задачи в `AIDD:HANDOFF_INBOX`. Свободный ввод после тикета используй как контекст ревью.
Следуй `aidd/AGENTS.md` и канону `aidd/docs/prompting/conventions.md` (pack‑first/read‑budget).

## Входные артефакты
- Diff/PR.
- `aidd/docs/prd/$1.prd.md`, `aidd/docs/plan/$1.md`, `aidd/docs/tasklist/$1.md`.
- `aidd/docs/spec/$1.spec.yaml` (если есть).
- Логи тестов/гейтов (если есть), `aidd/reports/reviewer/$1/<scope_key>.json`.

## Evidence Read Policy (RLM-first)
- Primary evidence: `aidd/reports/research/<ticket>-rlm.pack.json` (pack-first summary).
- Slice on demand: `${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh --ticket <ticket> --query "<token>"`.
- Use raw `rg` only for spot-checks.

## Когда запускать
- После `/feature-dev-aidd:implement`, до `/feature-dev-aidd:qa`.
- Повторять до снятия блокеров.

## Автоматические хуки и переменные
- `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh review` фиксирует стадию `review`.
- `${CLAUDE_PLUGIN_ROOT}/tools/loop-pack.sh --ticket $1 --stage review` создаёт loop pack и задаёт `aidd/docs/.active.json` (ticket/work_item).
- Команда должна запускать саб-агента **feature-dev-aidd:reviewer**.
- `${CLAUDE_PLUGIN_ROOT}/tools/review-report.sh --ticket $1` сохраняет отчёт ревью в `aidd/reports/reviewer/$1/<scope_key>.json`.
- `${CLAUDE_PLUGIN_ROOT}/tools/review-pack.sh --ticket $1` создаёт `review.latest.pack.md` и `review.fix_plan.json` (при REVISE) для следующего implement (per scope_key).
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
- Целевой файл: `aidd/reports/context/$1.pack.md` (rolling pack).
- Рекомендуемый CLI: `${CLAUDE_PLUGIN_ROOT}/tools/context-pack.sh --ticket $1 --agent review --stage review --template aidd/reports/context/template.context-pack.md --output aidd/reports/context/$1.pack.md --read-next "<loop pack>" --read-next "<review pack if exists>" --read-next "<rolling context>" --artefact-link "<artifact: path>" --what-to-do "<review focus>" --user-note "$ARGUMENTS"`.
- Заполни поля stage/agent/read_next/artefact_links/what_to_do/user_note под review.
- Read next: loop pack → review pack (если есть) → rolling context.
- What to do now: review diff vs plan/tasklist, add handoff findings.
- User note: $ARGUMENTS.

## Пошаговый план
1. Команда (до subagent): зафиксируй стадию `review` через `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh review` и активную фичу через `${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh "$1"`.
2. Команда (до subagent): создай loop pack `${CLAUDE_PLUGIN_ROOT}/tools/loop-pack.sh --ticket $1 --stage review`.
3. Команда (до subagent): собери Context Pack `${CLAUDE_PLUGIN_ROOT}/tools/context-pack.sh --ticket $1 --agent review --stage review --template aidd/reports/context/template.context-pack.md --output aidd/reports/context/$1.pack.md --read-next "<loop pack>" --read-next "<review pack if exists>" --read-next "<rolling context>" --artefact-link "<artifact: path>" --what-to-do "<review focus>" --user-note "$ARGUMENTS"`; если pack не записался — верни `Status: BLOCKED`.
4. Команда → subagent: **Use the feature-dev-aidd:reviewer subagent. First action: Read loop pack, затем (если есть) `review.latest.pack.md`, затем `aidd/reports/context/$1.pack.md`.** Если excerpt в loop pack содержит Goal/DoD/Boundaries/Expected paths/Size budget/Tests/Acceptance — запрещено читать полный tasklist/PRD/Plan/Research/Spec.
5. Subagent: обновляет tasklist (AIDD:CHECKLIST_REVIEW, handoff, front‑matter `Status/Updated`, `AIDD:CONTEXT_PACK Status`) и использует только `READY|WARN|BLOCKED` (исправимые дефекты → `WARN`/`REVISE`).
6. Subagent: пишет findings JSON через `AIDD:WRITE_JSON` в `aidd/reports/reviewer/$1/<scope_key>.findings.json`; при verdict=REVISE пишет Fix Plan JSON в `aidd/reports/reviewer/$1/<scope_key>.fix_plan.json`.
7. Subagent: при verdict=REVISE включает Fix Plan (структурированный блок; каждый blocking finding отражён).
8. Subagent: выполняет verify results (review evidence) и не выставляет финальный non‑BLOCKED статус без верификации (кроме `profile: none`).
9. Команда (после subagent): проверь scope через `${CLAUDE_PLUGIN_ROOT}/tools/diff-boundary-check.sh --ticket $1` и зафиксируй результат (`OK|OUT_OF_SCOPE <path>|FORBIDDEN <path>|NO_BOUNDARIES_DEFINED`) в ответе/логах; `OUT_OF_SCOPE/NO_BOUNDARIES_DEFINED → Status: WARN` + handoff, `FORBIDDEN → Status: BLOCKED`.
10. Команда (после subagent): сохрани отчёт ревью через `${CLAUDE_PLUGIN_ROOT}/tools/review-report.sh --ticket $1 --findings-file "aidd/reports/reviewer/$1/<scope_key>.findings.json" --fix-plan-file "aidd/reports/reviewer/$1/<scope_key>.fix_plan.json"` (Fix Plan обязателен при REVISE).
11. Команда (после subagent): собери review pack `${CLAUDE_PLUGIN_ROOT}/tools/review-pack.sh --ticket $1` и убедись, что `review.fix_plan.json` создан при REVISE (review-report авто‑синхронизирует pack при наличии loop-pack/work_item в `aidd/docs/.active.json`, но явный вызов остаётся обязательным).
12. Команда (после subagent): запиши stage result `${CLAUDE_PLUGIN_ROOT}/tools/stage-result.sh --ticket $1 --stage review --result <blocked|continue|done> --verdict <SHIP|REVISE|BLOCKED> --work-item-key <iteration_id=...>` (work_item_key бери из `aidd/docs/.active.json`; `done` при SHIP, `continue` при REVISE; `blocked` только при missing artifacts/evidence или `FORBIDDEN`; `tests_required=soft` + missing/skipped → `verdict=REVISE`/`result=continue`, `tests_required=hard` → `verdict=BLOCKED`/`result=blocked`).
13. Команда (после subagent): всегда обнови reviewer‑маркер через `${CLAUDE_PLUGIN_ROOT}/tools/reviewer-tests.sh --ticket $1 --status required|optional|skipped|not-required` (выбери статус явно, даже если тесты не нужны).
14. Команда (после subagent): запусти `${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh --source review --append --ticket $1`.
15. Команда (после subagent): подтверди прогресс через `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source review --ticket $1`.
16. Команда (после subagent): сформируй финальный статус через `${CLAUDE_PLUGIN_ROOT}/tools/status-summary.sh --ticket $1 --stage review` и используй его в ответе (single source of truth).
17. Если tasklist невалиден — `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh --ticket $1` → `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-normalize.sh --ticket $1 --fix`.

## Fail-fast и вопросы
- Нет актуального tasklist/плана — остановись и попроси обновить артефакты.
- Если diff не соответствует тикету — `Status: WARN` + handoff (BLOCKED только при missing artifacts/evidence или `FORBIDDEN`).
- Если `aidd/reports/context/$1.pack.md` отсутствует после записи — верни `Status: BLOCKED`.
- Если `aidd/reports/context/$1.pack.md` содержит `<stage-specific goal>` — верни `Status: WARN` (reason_code: `review_context_pack_placeholder_warn`) и продолжай, считая loop pack основным источником.
- Если `aidd/docs/.active.json` не совпадает с `$1` или отсутствует work_item — верни `Status: BLOCKED` (reason_code: `review_active_ticket_mismatch` / `review_active_work_item_missing`).
- Если выбранный work_item не совпадает с `aidd/docs/.active.json` — верни `Status: BLOCKED` (reason_code: `review_work_item_mismatch`).
- Если `.active_mode=loop` и требуются ответы — `Status: BLOCKED` + handoff (без вопросов в чат).
- Любой ранний `BLOCKED` фиксируй через `${CLAUDE_PLUGIN_ROOT}/tools/stage-result.sh` (при необходимости `--allow-missing-work-item` + `--verdict BLOCKED`).
- Любой ранний `BLOCKED` (до subagent) всё равно выводит полный контракт: `Status/Work item key/Artifacts updated/Tests/Blockers/Handoff/Next actions`; если данных нет — `n/a`. `Tests: run` запрещён без tests_log → используй `Tests: skipped` + reason_code.

## Ожидаемый вывод
- Обновлённый `aidd/docs/tasklist/$1.md`.
- `Status: READY|WARN|BLOCKED`.
- `Work item key: iteration_id=...`.
- `Artifacts updated: <paths>`.
- `Tests: run|skipped|not-required <profile/summary/evidence>` (без tests_log → `skipped` + reason_code).
- `Blockers/Handoff: ...`.
- `Next actions: ...`.
- `AIDD:READ_LOG: <paths>`.
- Финальный `Status` должен совпадать с выводом `${CLAUDE_PLUGIN_ROOT}/tools/status-summary.sh`.
- Вердикт/Status должны совпадать с итоговым `review.latest.pack.md` и `stage.review.result.json` (если pack=REVISE → Status=WARN/REVISE, SHIP запрещён).
- Ответ содержит `Checkbox updated` (если есть).
- Итоговый Status в ответе: приоритет `stage_result` → `review report` → `review pack`. При расхождении выбери безопасный статус (BLOCKED > WARN > READY) и укажи `reason_code=sync_drift_warn`.

## Примеры CLI
- `/feature-dev-aidd:review ABC-123`
- `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh --ticket ABC-123`
