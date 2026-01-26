---
description: "Код-ревью и возврат замечаний в задачи"
argument-hint: "$1 [note...]"
lang: ru
prompt_version: 1.0.21
source_version: 1.0.21
allowed-tools:
  - Read
  - Edit
  - Write
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
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/tasklist-normalize.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/feature-dev-aidd:review` работает inline: фиксирует стадию и активную фичу, пишет Context Pack и явно запускает саб‑агента **feature-dev-aidd:reviewer** для проверки изменений перед QA и фиксации замечаний в tasklist. После ревью команда создаёт отчёт и формирует handoff‑задачи в `AIDD:HANDOFF_INBOX`. Свободный ввод после тикета используй как контекст ревью.
Следуй attention‑policy из `aidd/AGENTS.md` и начни с `aidd/docs/anchors/review.md`.

## Входные артефакты
- Diff/PR.
- `aidd/docs/prd/$1.prd.md`, `aidd/docs/plan/$1.md`, `aidd/docs/tasklist/$1.md`.
- `aidd/docs/spec/$1.spec.yaml` (если есть).
- Логи тестов/гейтов (если есть), `aidd/reports/reviewer/$1.json`.

## Evidence Read Policy (RLM-first)
- Primary evidence: `aidd/reports/research/<ticket>-rlm.pack.*` (pack-first summary).
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
- `${CLAUDE_PLUGIN_ROOT}/tools/review-report.sh --ticket $1` сохраняет отчёт ревью в `aidd/reports/reviewer/$1.json`.
- `${CLAUDE_PLUGIN_ROOT}/tools/review-pack.sh --ticket $1` создаёт `review.latest.pack.md` для следующего implement.
- `${CLAUDE_PLUGIN_ROOT}/tools/reviewer-tests.sh --ticket $1 --status required|optional|skipped|not-required` управляет обязательностью тестов (`--clear` удаляет маркер).
- `${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh --source review --append --ticket $1` добавляет handoff‑задачи в `AIDD:HANDOFF_INBOX`.
- `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source review --ticket $1` фиксирует новые `[x]`.
- При проблемах tasklist используй `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh --ticket $1` и нормализацию `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-normalize.sh --ticket $1 --fix`.

## Что редактируется
- `aidd/docs/tasklist/$1.md` (замечания, прогресс).
- `aidd/reports/reviewer/$1.json`.

## Context Pack (шаблон)
Файл: `aidd/reports/context/$1.review.pack.md`.

```md
# AIDD Context Pack — review
ticket: $1
stage: review
agent: feature-dev-aidd:reviewer
generated_at: <UTC ISO-8601>

## Paths
- plan: aidd/docs/plan/$1.md
- tasklist: aidd/docs/tasklist/$1.md
- prd: aidd/docs/prd/$1.prd.md
- arch_profile: aidd/docs/architecture/profile.md
- loop_pack: aidd/reports/loops/$1/<work_item_key>.loop.pack.md
- review_pack: aidd/reports/loops/$1/review.latest.pack.md (if exists)
- spec: aidd/docs/spec/$1.spec.yaml (if exists)
- research: aidd/docs/research/$1.md (if exists)
- test_policy: aidd/.cache/test-policy.env (if exists)
- review_report: aidd/reports/reviewer/$1.json (if exists)

## What to do now
- Review diff vs plan/tasklist, add handoff findings.

## User note
- $ARGUMENTS

## Git snapshot (optional)
- branch: <git rev-parse --abbrev-ref HEAD>
- diffstat: <git diff --stat>
```

## Пошаговый план
1. Команда (до subagent): зафиксируй стадию `review` через `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh review` и активную фичу через `${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh "$1"`.
2. Команда (до subagent): создай loop pack `${CLAUDE_PLUGIN_ROOT}/tools/loop-pack.sh --ticket $1 --stage review`.
3. Команда (до subagent): собери Context Pack `aidd/reports/context/$1.review.pack.md` по шаблону W79-10.
4. Команда → subagent: **Use the feature-dev-aidd:reviewer subagent. First action: Read loop pack, затем `aidd/reports/context/$1.review.pack.md`.**
5. Subagent: обновляет tasklist (AIDD:CHECKLIST_REVIEW, handoff, front‑matter `Status/Updated`, `AIDD:CONTEXT_PACK Status`).
6. Команда (после subagent): проверь scope через `${CLAUDE_PLUGIN_ROOT}/tools/diff-boundary-check.sh --ticket $1` (при FAIL — BLOCKED).
7. Команда (после subagent): сохрани отчёт ревью через `${CLAUDE_PLUGIN_ROOT}/tools/review-report.sh --ticket $1`.
8. Команда (после subagent): собери review pack `${CLAUDE_PLUGIN_ROOT}/tools/review-pack.sh --ticket $1`.
9. Команда (после subagent): при необходимости запроси автотесты через `${CLAUDE_PLUGIN_ROOT}/tools/reviewer-tests.sh --ticket $1 --status required|optional|skipped|not-required` (или `--clear`).
10. Команда (после subagent): запусти `${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh --source review --append --ticket $1`.
11. Команда (после subagent): подтверди прогресс через `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source review --ticket $1`.
12. Если tasklist невалиден — `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh --ticket $1` → `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-normalize.sh --ticket $1 --fix`.

## Fail-fast и вопросы
- Нет актуального tasklist/плана — остановись и попроси обновить артефакты.
- Если diff не соответствует тикету — остановись и согласуй объём.

## Ожидаемый вывод
- Обновлённый `aidd/docs/tasklist/$1.md`.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/feature-dev-aidd:review ABC-123`
- `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh --ticket ABC-123`
