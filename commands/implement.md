---
description: "Реализация фичи по плану: малые итерации + управляемые проверки"
argument-hint: "$1 [note...] [test=fast|targeted|full|none] [tests=<filters>] [tasks=<task1,task2>]"
lang: ru
prompt_version: 1.1.20
source_version: 1.1.20
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(sed:*)"
  - "Bash(cat:*)"
  - "Bash(xargs:*)"
  - "Bash(./gradlew:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/hooks/format-and-test.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/progress.sh:*)"
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
Команда `/feature-dev-aidd:implement` работает inline: фиксирует стадию и активную фичу, при необходимости обновляет `test-policy.env`, пишет Context Pack и явно запускает саб‑агента **agent-feature-dev-aidd:implementer** для следующей итерации по плану и tasklist. Фокус — малые изменения и управляемые проверки. Свободный ввод после тикета используйте как контекст для текущей итерации.
Следуй attention‑policy из `aidd/AGENTS.md` и начни с `aidd/docs/anchors/implement.md`.

## Входные артефакты
- `aidd/docs/plan/$1.md`.
- `aidd/docs/tasklist/$1.md`.
- `aidd/docs/spec/$1.spec.yaml` (если есть).
- `aidd/docs/prd/$1.prd.md`, `aidd/docs/research/$1.md` — при необходимости.

## Когда запускать
- После `/feature-dev-aidd:tasks-new`, когда план и оба ревью готовы (Plan Review + PRD Review через `/feature-dev-aidd:review-spec`).
- Если нужен уточняющий контекст — предварительно запусти `/feature-dev-aidd:spec-interview` (опционально).
- Повторять на каждой итерации разработки.

## Автоматические хуки и переменные
- `${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh $1` фиксирует активную фичу.
- `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh implement` фиксирует стадию `implement`.
- Команда должна запускать саб-агента **agent-feature-dev-aidd:implementer**.
- `${CLAUDE_PLUGIN_ROOT}/hooks/format-and-test.sh` запускается на Stop/SubagentStop и читает `aidd/.cache/test-policy.env` (управляется `SKIP_AUTO_TESTS`, `FORMAT_ONLY`, `TEST_SCOPE`, `STRICT_TESTS`, `AIDD_TEST_PROFILE`, `AIDD_TEST_TASKS`, `AIDD_TEST_FILTERS`, `AIDD_TEST_FORCE`).
- `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source implement --ticket $1` проверяет наличие новых `- [x]`.
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
Файл: `aidd/reports/context/$1.implement.pack.md`.

```md
# AIDD Context Pack — implement
ticket: $1
stage: implement
agent: agent-feature-dev-aidd:implementer
generated_at: <UTC ISO-8601>

## Paths
- plan: aidd/docs/plan/$1.md
- tasklist: aidd/docs/tasklist/$1.md
- prd: aidd/docs/prd/$1.prd.md
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
2. Команда (до subagent): если переданы `test=...`, `tasks=...`, `tests=...` — обнови `aidd/.cache/test-policy.env`; иначе оставь существующий policy без изменений. Команда — единственный владелец записи.
3. Команда (до subagent): собери Context Pack `aidd/reports/context/$1.implement.pack.md` по шаблону W79-10.
4. Команда → subagent: **Use the agent-feature-dev-aidd:implementer subagent. First action: Read `aidd/reports/context/$1.implement.pack.md`.**
5. Subagent: реализует следующий пункт, обновляет tasklist.
6. Команда (после subagent): подтверди прогресс через `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source implement --ticket $1`.

## Fail-fast и вопросы
- Нет plan/tasklist или ревью не готовы — остановись и попроси завершить предыдущие шаги.
- Падающие тесты или блокеры — остановись до исправления/согласования.

## Ожидаемый вывод
- Обновлённый код и `aidd/docs/tasklist/$1.md`.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Test profile`, `Tests run`, `Next actions`.

## Примеры CLI
- `/feature-dev-aidd:implement ABC-123`
