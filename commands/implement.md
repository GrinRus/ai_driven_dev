---
description: "Реализация фичи по плану: малые итерации + управляемые проверки"
argument-hint: "$1 [note...] [test=fast|targeted|full|none] [tests=<filters>] [tasks=<task1,task2>]"
lang: ru
prompt_version: 1.1.34
source_version: 1.1.34
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
Следуй attention‑policy из `aidd/AGENTS.md`, канону `aidd/docs/prompting/conventions.md` и начни с `aidd/docs/anchors/implement.md`.

## Входные артефакты
- `aidd/docs/plan/$1.md`.
- `aidd/docs/tasklist/$1.md`.
- `aidd/docs/spec/$1.spec.yaml` (если есть).
- `aidd/docs/prd/$1.prd.md`, `aidd/docs/research/$1.md` — при необходимости.

## Evidence Read Policy (RLM-first)
- Primary evidence: `aidd/reports/research/<ticket>-rlm.pack.json` (pack-first summary).
- Slice on demand: `${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh --ticket <ticket> --query "<token>"`.
- Use raw `rg` only for spot-checks.
- Legacy `ast_grep` evidence is fallback-only.

## Когда запускать
- После `/feature-dev-aidd:tasks-new`, когда план и оба ревью готовы (Plan Review + PRD Review через `/feature-dev-aidd:review-spec`).
- Если нужен уточняющий контекст — предварительно запусти `/feature-dev-aidd:spec-interview` (опционально).
- Повторять на каждой итерации разработки.

## Автоматические хуки и переменные
- `${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh $1` фиксирует активную фичу.
- `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh implement` фиксирует стадию `implement`.
- `${CLAUDE_PLUGIN_ROOT}/tools/prd-check.sh --ticket $1` подтверждает PRD `Status: READY`.
- `${CLAUDE_PLUGIN_ROOT}/tools/loop-pack.sh --ticket $1 --stage implement` создаёт loop pack и задаёт `.active_ticket`/`.active_work_item`. Если pack не появился — `Status: BLOCKED`.
- Команда должна запускать саб-агента **feature-dev-aidd:implementer**.
- `${CLAUDE_PLUGIN_ROOT}/hooks/format-and-test.sh` запускается на Stop/SubagentStop и читает `aidd/.cache/test-policy.env` (управляется `SKIP_AUTO_TESTS`, `FORMAT_ONLY`, `TEST_SCOPE`, `STRICT_TESTS`, `AIDD_TEST_PROFILE`, `AIDD_TEST_TASKS`, `AIDD_TEST_FILTERS`, `AIDD_TEST_FORCE`).
- `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source implement --ticket $1` проверяет наличие новых `- [x]`.
- `${CLAUDE_PLUGIN_ROOT}/tools/stage-result.sh` записывает `stage_result` (обязателен для loop-step).
- При рассинхроне tasklist прогоняй `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh --ticket $1` и, если нужно, `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-normalize.sh --ticket $1 --fix`.
- Не дублируй запуск `format-and-test.sh` вручную — хук уже управляет тест-бюджетом и дедупом.

## Test policy (FAST/TARGETED/FULL/NONE)
Профиль задаётся через `aidd/.cache/test-policy.env`. Policy управляет **чем** запускать, а reviewer gate — **обязательностью/эскалацией**. Если аргументы `test=.../tests=.../tasks=...` не переданы — не перезаписывай существующий `test-policy.env`. Команда — единственный владелец записи; implementer не создаёт файл.

Пример файла:
```
AIDD_TEST_PROFILE=fast
AIDD_TEST_TASKS=:module:test
AIDD_TEST_FILTERS=com.acme.CheckoutTest
```

Decision matrix (default: `fast`):
- `fast`: небольшие правки в одном модуле, низкий риск, быстрые проверки.
- `targeted`: нужен узкий прогон (`AIDD_TEST_TASKS` и/или `AIDD_TEST_FILTERS`).
- `full`: изменения общих конфигов/ядра/инфры, высокий риск регрессий.
- `none`: только документация/метаданные, без кода.

## Что редактируется
- Код/конфиги и `aidd/docs/tasklist/$1.md` (прогресс и чекбоксы).

## Context Pack (шаблон)
- Шаблон: `aidd/reports/context/template.context-pack.md`.
- Целевой файл: `aidd/reports/context/$1.implement.pack.md` (stage/agent/paths/what-to-do заполняются под implement).
- Paths: plan, tasklist, prd, arch_profile, loop_pack, review_pack (if exists), spec/research/test_policy (if exists).
- What to do now: take next item from AIDD:NEXT_3, limit to 1 checkbox.
- User note: $ARGUMENTS.

## Пошаговый план
1. Команда (до subagent): зафиксируй активную фичу через `${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh "$1"` и стадию `implement` через `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh implement`.
2. Команда (до subagent): проверь PRD через `${CLAUDE_PLUGIN_ROOT}/tools/prd-check.sh --ticket $1` (при ошибке → `BLOCKED`).
3. Команда (до subagent): создай loop pack `${CLAUDE_PLUGIN_ROOT}/tools/loop-pack.sh --ticket $1 --stage implement`.
4. Команда (до subagent): убедись, что `aidd/reports/loops/$1/<scope_key>.loop.pack.md` существует (используй `.active_work_item` → scope_key); если pack отсутствует — верни `Status: BLOCKED` и попроси rerun.
5. Команда (до subagent): если переданы `test=...`, `tasks=...`, `tests=...` — обнови `aidd/.cache/test-policy.env`; иначе оставь существующий policy без изменений. Команда — единственный владелец записи.
6. Команда (до subagent): собери Context Pack `aidd/reports/context/$1.implement.pack.md` по шаблону `aidd/reports/context/template.context-pack.md`.
7. Команда → subagent: **Use the feature-dev-aidd:implementer subagent. First action: Read loop pack, затем `aidd/reports/context/$1.implement.pack.md`.**
8. Subagent: реализует следующий пункт, обновляет tasklist (`AIDD:ITERATIONS_FULL`/`AIDD:HANDOFF_INBOX`), обновляет `AIDD:NEXT_3`, добавляет ссылку/доказательство в `AIDD:PROGRESS_LOG`.
9. Subagent: выполняет verify results (tests/QA evidence) и не выставляет финальный non‑BLOCKED статус без верификации (кроме `profile: none`).
10. Команда (после subagent): проверь scope через `${CLAUDE_PLUGIN_ROOT}/tools/diff-boundary-check.sh --ticket $1` и зафиксируй результат (`OK|OUT_OF_SCOPE <path>|FORBIDDEN <path>|NO_BOUNDARIES_DEFINED`) в ответе/логах; `OUT_OF_SCOPE/NO_BOUNDARIES_DEFINED → Status: WARN` + handoff (`AIDD:OUT_OF_SCOPE_BACKLOG`, `reason_code=out_of_scope_warn|no_boundaries_defined_warn`), `FORBIDDEN → Status: BLOCKED` и запросить откат/новый work_item.
11. Команда (после subagent): подтверди прогресс через `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source implement --ticket $1`.
12. Команда (после subagent): запиши stage result `${CLAUDE_PLUGIN_ROOT}/tools/stage-result.sh --ticket $1 --stage implement --result <blocked|continue> --work-item-key <iteration_id=...>` (work_item_key бери из `.active_work_item`; `blocked` только при `FORBIDDEN`/отсутствии обязательных артефактов/evidence; `OUT_OF_SCOPE/NO_BOUNDARIES_DEFINED` → `continue` + `--reason-code out_of_scope_warn|no_boundaries_defined_warn`).
13. При рассинхроне tasklist — `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh --ticket $1`, при необходимости `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-normalize.sh --ticket $1 --fix`.

## Fail-fast и вопросы
- Нет plan/tasklist или ревью не готовы — остановись и попроси завершить предыдущие шаги.
- Падающие тесты или блокеры — остановись до исправления/согласования.
- Если `.active_mode=loop` и требуются ответы — `Status: BLOCKED` + handoff (без вопросов в чат).

## Ожидаемый вывод
- Обновлённый код и `aidd/docs/tasklist/$1.md`.
- Ответ содержит `Checkbox updated`, `Status`, `Work item key`, `Artifacts updated`, `Tests`, `Next actions` (output‑контракт соблюдён).

## Примеры CLI
- `/feature-dev-aidd:implement ABC-123`
- `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-normalize.sh --ticket ABC-123 --dry-run`
