---
description: "Реализация фичи по плану: малые итерации + управляемые проверки"
argument-hint: "<TICKET> [note...] [test=fast|targeted|full|none] [tests=<filters>] [tasks=<task1,task2>]"
lang: ru
prompt_version: 1.1.14
source_version: 1.1.14
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
  - "Bash(PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli set-active-stage:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT:-.}/hooks/format-and-test.sh:*)"
  - "Bash(PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli progress:*)"
  - "Bash(git:*)"
  - "Bash(PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli set-active-feature:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/implement` запускает саб-агента **implementer** для следующей итерации по плану и tasklist. Фокус — малые изменения и управляемые проверки. Свободный ввод после тикета используйте как контекст для текущей итерации.
Следуй attention‑policy из `aidd/AGENTS.md` и начни с `aidd/docs/anchors/implement.md`.

## Входные артефакты
- `@aidd/docs/plan/<ticket>.md`.
- `@aidd/docs/tasklist/<ticket>.md`.
- `@aidd/docs/spec/<ticket>.spec.yaml` (если есть).
- `@aidd/docs/prd/<ticket>.prd.md`, `@aidd/docs/research/<ticket>.md` — при необходимости.

## Когда запускать
- После `/tasks-new`, когда план и оба ревью готовы (Plan Review + PRD Review через `/review-spec`).
- Если нужен уточняющий контекст — предварительно запусти `/spec-interview` (опционально).
- Повторять на каждой итерации разработки.

## Автоматические хуки и переменные
- `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli set-active-feature --target . <ticket>` фиксирует активную фичу.
- `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli set-active-stage implement` фиксирует стадию `implement`.
- Команда должна запускать саб-агента **implementer** (Claude: Run agent → implementer).
- `${CLAUDE_PLUGIN_ROOT:-.}/hooks/format-and-test.sh` запускается на Stop/SubagentStop и читает `aidd/.cache/test-policy.env` (управляется `SKIP_AUTO_TESTS`, `FORMAT_ONLY`, `TEST_SCOPE`, `STRICT_TESTS`, `AIDD_TEST_PROFILE`, `AIDD_TEST_TASKS`, `AIDD_TEST_FILTERS`, `AIDD_TEST_FORCE`).
- `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli progress --source implement --ticket <ticket>` проверяет наличие новых `- [x]`.
- Не дублируй запуск `format-and-test.sh` вручную — хук уже управляет тест-бюджетом и дедупом.

## Test policy (FAST/TARGETED/FULL/NONE)
Профиль задаётся через `aidd/.cache/test-policy.env`. Policy управляет **чем** запускать, а reviewer gate — **обязательностью/эскалацией**. Если аргументы `test=.../tests=.../tasks=...` не переданы — не перезаписывай существующий `test-policy.env`.

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
- Код/конфиги и `aidd/docs/tasklist/<ticket>.md` (прогресс и чекбоксы).

## Пошаговый план
1. Зафиксируй активную фичу (`set-active-feature`) и стадию `implement`.
2. Если переданы аргументы `test=...`, `tasks=...`, `tests=...` — задай test policy в `aidd/.cache/test-policy.env`; иначе оставь существующий policy без изменений.
3. Запусти саб-агента **implementer** и передай контекст итерации.
4. Убедись, что tasklist обновлён и прогресс подтверждён через `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli progress`.

## Fail-fast и вопросы
- Нет plan/tasklist или ревью не готовы — остановись и попроси завершить предыдущие шаги.
- Падающие тесты или блокеры — остановись до исправления/согласования.

## Ожидаемый вывод
- Обновлённый код и `aidd/docs/tasklist/<ticket>.md`.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Test profile`, `Tests run`, `Next actions`.

## Примеры CLI
- `/implement ABC-123`
