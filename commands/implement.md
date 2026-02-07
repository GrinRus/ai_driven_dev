---
description: "Реализация фичи по плану: малые итерации + управляемые проверки"
argument-hint: "$1 [note...] [test=fast|targeted|full|none] [tests=<filters>] [tasks=<task1,task2>]"
lang: ru
prompt_version: 1.1.39
source_version: 1.1.39
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(sed:*)"
  - "Bash(cat:*)"
  - "Bash(xargs:*)"
  - "Bash(npm:*)"
  - "Bash(pnpm:*)"
  - "Bash(yarn:*)"
  - "Bash(pytest:*)"
  - "Bash(python:*)"
  - "Bash(go:*)"
  - "Bash(mvn:*)"
  - "Bash(make:*)"
  - "Bash(./gradlew:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/prd-check.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/loop-pack.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/diff-boundary-check.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/hooks/format-and-test.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/progress.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/stage-result.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/status-summary.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/tasklist-normalize.sh:*)"
  - "Bash(git status:*)"
  - "Bash(git diff:*)"
  - "Bash(git log:*)"
  - "Bash(git show:*)"
  - "Bash(git rev-parse:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/feature-dev-aidd:implement` работает inline: фиксирует стадию и активную фичу, формирует loop pack, при необходимости обновляет `test-policy.env`, пишет Context Pack и явно запускает саб‑агента **feature-dev-aidd:implementer** для следующей итерации по plan/tasklist. Фокус — малые изменения и управляемые проверки. Свободный ввод после тикета используйте как контекст для текущей итерации.
Следуй `aidd/AGENTS.md` и канону `aidd/docs/prompting/conventions.md` (pack‑first/read‑budget).

## Входные артефакты
- `aidd/docs/plan/$1.md`.
- `aidd/docs/tasklist/$1.md`.
- `aidd/docs/spec/$1.spec.yaml` (если есть).
- `aidd/docs/prd/$1.prd.md`, `aidd/docs/research/$1.md` — при необходимости.

## Evidence Read Policy (RLM-first)
- Primary evidence: `aidd/reports/research/<ticket>-rlm.pack.json` (pack-first summary).
- Slice on demand: `${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh --ticket <ticket> --query "<token>"`.
- Use raw `rg` only for spot-checks.

## Когда запускать
- После `/feature-dev-aidd:tasks-new`, когда план и оба ревью готовы (Plan Review + PRD Review через `/feature-dev-aidd:review-spec`).
- Если нужен уточняющий контекст — предварительно запусти `/feature-dev-aidd:spec-interview` (опционально).
- Повторять на каждой итерации разработки.

## Автоматические хуки и переменные
- `${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh $1` фиксирует активную фичу.
- `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh implement` фиксирует стадию `implement`.
- `${CLAUDE_PLUGIN_ROOT}/tools/prd-check.sh --ticket $1` подтверждает PRD `Status: READY`.
- `${CLAUDE_PLUGIN_ROOT}/tools/loop-pack.sh --ticket $1 --stage implement` создаёт loop pack и задаёт `aidd/docs/.active.json` (ticket/work_item). При REVISE переиспользует текущий work_item (не двигает `AIDD:NEXT_3`). Если pack не появился — `Status: BLOCKED`.
- Команда должна запускать саб-агента **feature-dev-aidd:implementer**.
- `${CLAUDE_PLUGIN_ROOT}/hooks/format-and-test.sh` запускается на Stop/SubagentStop и читает `aidd/.cache/test-policy.env` (управляется `SKIP_AUTO_TESTS`, `FORMAT_ONLY`, `TEST_SCOPE`, `STRICT_TESTS`, `AIDD_TEST_PROFILE`, `AIDD_TEST_TASKS`, `AIDD_TEST_FILTERS`, `AIDD_TEST_FORCE`).
- `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source implement --ticket $1` проверяет наличие новых `- [x]`.
- `${CLAUDE_PLUGIN_ROOT}/tools/stage-result.sh` записывает `stage_result` (обязателен для loop-step).
- При рассинхроне tasklist прогоняй `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh --ticket $1` и, если нужно, `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-normalize.sh --ticket $1 --fix`.
- Не дублируй запуск `format-and-test.sh` вручную — хук уже управляет тест-бюджетом и дедупом.

## Test policy (IMPLEMENT = NO TESTS)
- В implement тесты запрещены: `Tests: not-required` или `Tests: skipped` с reason.
- Допускается только форматирование; тестовые профили (fast/targeted/full) задаются на review/qa.
- Если переданы `test=.../tests=.../tasks=...` — не применяй их на implement; оставь политику без изменений.

## Что редактируется
- Код/конфиги и `aidd/docs/tasklist/$1.md` (прогресс и чекбоксы).

## Context Pack (шаблон)
- Шаблон: `aidd/reports/context/template.context-pack.md`.
- Целевой файл: `aidd/reports/context/$1.pack.md` (rolling pack).
- Заполни поля stage/agent/read_next/artefact_links/what_to_do/user_note под implement.
- Read next: loop pack → review pack (если есть) → rolling context.
- What to do now: take next item from AIDD:NEXT_3, limit to 1 checkbox.
- User note: $ARGUMENTS.

## Пошаговый план
1. Команда (до subagent): зафиксируй активную фичу через `${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh "$1"` и стадию `implement` через `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh implement`.
2. Команда (до subagent): проверь PRD через `${CLAUDE_PLUGIN_ROOT}/tools/prd-check.sh --ticket $1` (при ошибке → `BLOCKED`).
3. Команда (до subagent): создай loop pack `${CLAUDE_PLUGIN_ROOT}/tools/loop-pack.sh --ticket $1 --stage implement`.
4. Команда (до subagent): убедись, что `aidd/reports/loops/$1/<scope_key>.loop.pack.md` существует (используй `aidd/docs/.active.json` → work_item → scope_key); если pack отсутствует — верни `Status: BLOCKED` и попроси rerun.
5. Команда (до subagent): если есть review pack и verdict=REVISE — убедись, что `review.fix_plan.json` существует; иначе `Status: BLOCKED`.
6. Команда (до subagent): на implement **не** обновляй `aidd/.cache/test-policy.env` и игнорируй `test=.../tasks=.../tests=...` (тесты запрещены).
7. Команда (до subagent): собери Context Pack через `${CLAUDE_PLUGIN_ROOT}/tools/context-pack.sh --ticket $1 --agent implement --stage implement --read-next "<loop pack>" --read-next "<review pack if exists>" --read-next "aidd/reports/context/$1.pack.md" --artefact-link "<artifact: path>" --what-to-do "<NEXT_3 item>" --user-note "$ARGUMENTS"`.
8. Команда → subagent: **Use the feature-dev-aidd:implementer subagent. First action: Read loop pack → review pack (если есть) → fix_plan.json (если verdict=REVISE) → `aidd/reports/context/$1.pack.md`.**
9. Subagent: реализует следующий пункт, обновляет tasklist (REVISE не закрывает чекбокс и не меняет `AIDD:NEXT_3`), добавляет ссылку/доказательство в `AIDD:PROGRESS_LOG`.
10. Subagent: верифицирует соответствие DoD и scope; тесты выполняются на review/qa.
11. Команда (после subagent): проверь scope через `${CLAUDE_PLUGIN_ROOT}/tools/diff-boundary-check.sh --ticket $1` и зафиксируй результат (`OK|OUT_OF_SCOPE <path>|FORBIDDEN <path>|NO_BOUNDARIES_DEFINED`) в ответе/логах; `OUT_OF_SCOPE/NO_BOUNDARIES_DEFINED → Status: WARN` + handoff (`AIDD:OUT_OF_SCOPE_BACKLOG`, `reason_code=out_of_scope_warn|no_boundaries_defined_warn|auto_boundary_extend_warn`), `FORBIDDEN → Status: BLOCKED` и запросить откат/новый work_item.
12. Команда (после subagent): подтверди прогресс через `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source implement --ticket $1`.
13. Команда (после subagent): запиши stage result `${CLAUDE_PLUGIN_ROOT}/tools/stage-result.sh --ticket $1 --stage implement --result <blocked|continue> --work-item-key <iteration_id=...>` (work_item_key бери из `aidd/docs/.active.json`; `blocked` только при `FORBIDDEN`/отсутствии обязательных артефактов/evidence; `OUT_OF_SCOPE/NO_BOUNDARIES_DEFINED` → `continue` + `--reason-code out_of_scope_warn|no_boundaries_defined_warn`; `tests_required=soft` + missing/skipped → `Status: WARN` (не `BLOCKED`), `tests_required=hard` → `BLOCKED`). При раннем `BLOCKED` без work_item используй `--allow-missing-work-item` + `--reason-code`.
14. Команда (после subagent): сформируй финальный статус через `${CLAUDE_PLUGIN_ROOT}/tools/status-summary.sh --ticket $1 --stage implement` и используй его в ответе (single source of truth).
15. При рассинхроне tasklist — `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh --ticket $1`, при необходимости `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-normalize.sh --ticket $1 --fix`.

## Fail-fast и вопросы
- Нет plan/tasklist или ревью не готовы — остановись и попроси завершить предыдущие шаги.
- Падающие проверки/форматирование или блокеры — остановись до исправления/согласования.
- Если `.active_mode=loop` и требуются ответы — `Status: BLOCKED` + handoff (без вопросов в чат).
- Любой ранний `BLOCKED` фиксируй через `${CLAUDE_PLUGIN_ROOT}/tools/stage-result.sh` (при необходимости `--allow-missing-work-item`).
- Любой ранний `BLOCKED` (до subagent) всё равно выводит полный контракт: `Status/Work item key/Artifacts updated/Tests/Blockers/Handoff/Next actions`; если данных нет — `n/a`. `Tests: run` запрещён без tests_log → используй `Tests: skipped` + reason_code.

## Ожидаемый вывод
- Обновлённый код и `aidd/docs/tasklist/$1.md`.
- `Status: READY|WARN|BLOCKED|PENDING`.
- Финальный `Status` должен совпадать с выводом `${CLAUDE_PLUGIN_ROOT}/tools/status-summary.sh`.
- `Work item key: iteration_id=...` (или `n/a` при раннем BLOCKED).
- `Artifacts updated: <paths>`.
- `Tests: run|skipped|not-required <profile/summary/evidence>` (без tests_log → `skipped` + reason_code).
- `Blockers/Handoff: ...`.
- `Next actions: ...`.
- `AIDD:READ_LOG: <paths>`.
- Ответ содержит `Checkbox updated` (если есть).

## Примеры CLI
- `/feature-dev-aidd:implement ABC-123`
- `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-normalize.sh --ticket ABC-123 --dry-run`
