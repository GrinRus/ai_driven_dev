---
description: "Реализация фичи по плану: малые итерации + управляемые проверки"
argument-hint: "$1 [note...] [test=fast|targeted|full|none] [tests=<filters>] [tasks=<task1,task2>]"
lang: ru
prompt_version: 1.1.28
source_version: 1.1.28
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
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/loop-pack.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/diff-boundary-check.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/hooks/format-and-test.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/progress.sh:*)"
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
Следуй attention‑policy из `aidd/AGENTS.md` и начни с `aidd/docs/anchors/implement.md`.

## Входные артефакты
- `aidd/docs/plan/$1.md`.
- `aidd/docs/tasklist/$1.md`.
- `aidd/docs/spec/$1.spec.yaml` (если есть).
- `aidd/docs/prd/$1.prd.md`, `aidd/docs/research/$1.md` — при необходимости.

## Evidence Read Policy (RLM-first)
- Primary evidence: `aidd/reports/research/<ticket>-rlm.pack.*` (pack-first summary).
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
- `${CLAUDE_PLUGIN_ROOT}/tools/loop-pack.sh --ticket $1 --stage implement` создаёт loop pack и задаёт `.active_ticket`/`.active_work_item`.
- Команда должна запускать саб-агента **feature-dev-aidd:implementer**.
- `${CLAUDE_PLUGIN_ROOT}/hooks/format-and-test.sh` запускается на Stop/SubagentStop и читает `aidd/.cache/test-policy.env` (управляется `SKIP_AUTO_TESTS`, `FORMAT_ONLY`, `TEST_SCOPE`, `STRICT_TESTS`, `AIDD_TEST_PROFILE`, `AIDD_TEST_TASKS`, `AIDD_TEST_FILTERS`, `AIDD_TEST_FORCE`).
- `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source implement --ticket $1` проверяет наличие новых `- [x]`.
- При рассинхроне tasklist прогоняй `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh --ticket $1` и, если нужно, `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-normalize.sh --ticket $1 --fix`.
- Не дублируй запуск `format-and-test.sh` вручную — хук уже управляет тест-бюджетом и дедупом.
- Для тестов/формата/запуска сначала используй project skills:
  - если есть `.claude/skills/<skill-id>/SKILL.md` → следуй им;
  - иначе если есть `.claude/commands/*.md` → следуй им (legacy);
  - иначе попытайся определить команды из repo; если не выходит — BLOCKED и запроси команды у пользователя.

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
Файл: `aidd/reports/context/$1.implement.pack.md`.

```md
# AIDD Context Pack — implement
ticket: $1
stage: implement
agent: feature-dev-aidd:implementer
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

## What to do now
- Take next item from AIDD:NEXT_3, limit to 1 checkbox.

## User note
- $ARGUMENTS

## Git snapshot (optional)
- branch: <git rev-parse --abbrev-ref HEAD>
- diffstat: <git diff --stat>
```

## Пошаговый план
1. Команда (до subagent): зафиксируй активную фичу через `${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh "$1"` и стадию `implement` через `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh implement`.
2. Команда (до subagent): создай loop pack `${CLAUDE_PLUGIN_ROOT}/tools/loop-pack.sh --ticket $1 --stage implement`.
3. Команда (до subagent): если переданы `test=...`, `tasks=...`, `tests=...` — обнови `aidd/.cache/test-policy.env`; иначе оставь существующий policy без изменений. Команда — единственный владелец записи.
4. Команда (до subagent): собери Context Pack `aidd/reports/context/$1.implement.pack.md` по шаблону W79-10.
5. Команда → subagent: **Use the feature-dev-aidd:implementer subagent. First action: Read loop pack, затем `aidd/reports/context/$1.implement.pack.md`.**
6. Subagent: реализует следующий пункт, обновляет tasklist (`AIDD:ITERATIONS_FULL`/`AIDD:HANDOFF_INBOX`), обновляет `AIDD:NEXT_3`, добавляет ссылку/доказательство в `AIDD:PROGRESS_LOG`.
7. Subagent: выполняет verify results (tests/QA evidence) и не выставляет финальный non‑BLOCKED статус без верификации (кроме `profile: none`).
8. Команда (после subagent): проверь scope через `${CLAUDE_PLUGIN_ROOT}/tools/diff-boundary-check.sh --ticket $1` (при FAIL — BLOCKED, попроси откатить лишние файлы или создать новый work_item).
9. Команда (после subagent): подтверди прогресс через `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source implement --ticket $1`.
10. При рассинхроне tasklist — `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh --ticket $1`, при необходимости `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-normalize.sh --ticket $1 --fix`.

## Fail-fast и вопросы
- Нет plan/tasklist или ревью не готовы — остановись и попроси завершить предыдущие шаги.
- Падающие тесты или блокеры — остановись до исправления/согласования.

## Ожидаемый вывод
- Обновлённый код и `aidd/docs/tasklist/$1.md`.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Test profile`, `Tests run`, `Next actions`.

## Примеры CLI
- `/feature-dev-aidd:implement ABC-123`
- `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-normalize.sh --ticket ABC-123 --dry-run`
