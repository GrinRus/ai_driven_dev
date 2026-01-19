# AGENTS (Repo development guide)

Этот файл — единая dev‑документация репозитория. Все dev‑правила и шаблоны живут здесь.

## Репозиторий и структура
- Runtime (плагин): `commands/`, `agents/`, `hooks/`, `tools/`, `.claude-plugin/`.
- Workspace‑шаблоны: `templates/aidd/` (копируются в `./aidd` через `/feature-dev-aidd:aidd-init`).
- Тесты: `tests/`.
- Repo tools: `tests/repo_tools/`.
- Backlog: `backlog.md` (корень).
- User‑артефакты: `aidd/**` (docs/reports/config/.cache).
- Derived‑артефакты: `aidd/docs/index/`, `aidd/reports/events/`, `aidd/.cache/`.

## Источник истины (dev vs user)
- `templates/aidd/**` — источник истины для workspace‑шаблонов; правим шаблоны, а не сгенерированный `aidd/**`.
- `aidd/**` появляется в workspace после `/feature-dev-aidd:aidd-init` и не хранится в repo (кроме шаблонов).
- `AGENTS.md` (корень) — dev‑гайд для репозитория; `templates/aidd/AGENTS.md` — user‑гайд для проектов.
- При изменении поведения: обновите `templates/aidd/**`, `AGENTS.md`, затем проверьте bootstrap (`/feature-dev-aidd:aidd-init`) и smoke.
- Workspace‑конфиги: `aidd/config/{gates.json,conventions.json,context_gc.json,allowed-deps.txt}` (источник — `templates/aidd/config/`).
- Hook wiring: `hooks/hooks.json` — обновляйте при добавлении/удалении хуков.
- Permissions/cadence: `aidd/.claude/settings.json` в workspace (если нужна настройка разрешений и cadence).

## Архитектура путей (plugin cache vs workspace)
- Плагин копируется в cache Claude Code: записи в `${CLAUDE_PLUGIN_ROOT}` недопустимы.
- Рабочий root всегда workspace (`./aidd`); только туда пишем `docs/`, `reports/`, `config/`.
- `${CLAUDE_PLUGIN_ROOT}` используется только для чтения ресурсов плагина (hooks/tools/templates).
- CWD хуков не гарантирован; корень проекта вычисляется из payload (cwd/workspace), без fallback на plugin root.

## Быстрые проверки (repo‑only)
- Полный линт + unit‑тесты: `tests/repo_tools/ci-lint.sh`.
- E2E smoke: `tests/repo_tools/smoke-workflow.sh`.
- Дополнительно (если нужно): `python3 -m unittest discover -s tests -t .`.
- Диагностика окружения: `${CLAUDE_PLUGIN_ROOT}/tools/doctor.sh`.
- Bootstrap шаблонов (workspace): `/feature-dev-aidd:aidd-init`.

## Минимальные зависимости
- `python3`, `rg`, `git` обязательны.
- Опционально: `tree_sitter_language_pack` для call‑graph (без него часть тестов может быть skipped).
- Для `tests/repo_tools/ci-lint.sh`: `shellcheck`, `markdownlint`, `yamllint` (иначе warn/skip).

## Локальный запуск entrypoints
- Инструменты: `CLAUDE_PLUGIN_ROOT=$PWD tools/<command>.sh ...`
- Хуки: `CLAUDE_PLUGIN_ROOT=$PWD hooks/<hook>.sh ...`

## Как добавлять фичи и команды (шаблон)
1. Runtime‑entrypoint: `tools/<command>.sh` (shebang python, bootstrap `CLAUDE_PLUGIN_ROOT`).
2. Логика команды: `tools/<command>.py` (или используйте существующий модуль).
3. Документация: обновите `commands/*.md` и/или `agents/*.md` (allowed‑tools + примеры).
4. Хуки: если команда участвует в workflow, добавьте вызов в `hooks/hooks.json`.
5. Шаблоны: если нужны новые workspace‑файлы — обновите `templates/aidd/**`, затем проверьте `/feature-dev-aidd:aidd-init`.
6. Тесты: unit в `tests/`, repo tooling/CI helpers — в `tests/repo_tools/`.
7. Prompt‑версии: после правок в `commands/`/`agents/` обновите `prompt_version` и прогоните `tests/repo_tools/prompt-version` + `tests/repo_tools/lint-prompts.py`.
8. Метаданные: при user‑facing изменениях обновите `CHANGELOG.md` и версии в `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` (если требуется).

## Workflow (кратко)
Канонические стадии: `idea → research → plan → review-plan → review-prd → tasklist → implement → review → qa`.

Ключевые команды:
- Идея: `/feature-dev-aidd:idea-new <ticket> [slug-hint]` → PRD + `analyst`.
- Research: `${CLAUDE_PLUGIN_ROOT}/tools/research.sh --ticket <ticket> --auto --deep-code` → `/feature-dev-aidd:researcher <ticket>`.
- План: `/feature-dev-aidd:plan-new <ticket>`.
- Review‑spec (plan + PRD): `/feature-dev-aidd:review-spec <ticket>`.
- Тасклист: `/feature-dev-aidd:tasks-new <ticket>`.
- Реализация: `/feature-dev-aidd:implement <ticket>` (гейтит `gate-workflow`, auto `format-and-test`).
- Ревью: `/feature-dev-aidd:review <ticket>`.
- QA: `/feature-dev-aidd:qa <ticket>` → отчёт `aidd/reports/qa/<ticket>.json`.

Agent‑first правило: сначала читаем артефакты (`aidd/docs/**`, `aidd/reports/**`), запускаем разрешённые команды (`rg`, `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh`, тесты), затем задаём вопросы пользователю.

## Кастомизация (минимум)
- `.claude/settings.json`: permissions и automation/tests cadence (`on_stop|checkpoint|manual`).
- `aidd/config/gates.json`:
  - `feature_ticket_source`, `feature_slug_hint_source`
  - `prd_review`, `plan_review`, `researcher`, `analyst`
  - `tests_required` (`disabled|soft|hard`), `tests_gate`
  - `deps_allowlist`
  - `qa.debounce_minutes`
  - `tasklist_progress`
- Важные env:
  - `SKIP_AUTO_TESTS`, `SKIP_FORMAT`, `FORMAT_ONLY`, `TEST_SCOPE`, `STRICT_TESTS`
  - `AIDD_TEST_PROFILE`, `AIDD_TEST_PROFILE_DEFAULT`, `AIDD_TEST_TASKS`, `AIDD_TEST_FILTERS`, `AIDD_TEST_FORCE`
  - `AIDD_TEST_LOG`, `AIDD_TEST_LOG_TAIL_LINES`, `AIDD_TEST_CHECKPOINT`

## Prompt versioning
- Semver: `MAJOR.MINOR.PATCH`.
- `source_version` всегда равен `prompt_version` для RU.
- Команды:
  - `python3 tests/repo_tools/prompt-version bump --root <workflow-root> --prompts <name> --kind agent|command --lang ru --part <major|minor|patch>`
  - `python3 tests/repo_tools/lint-prompts.py --root <workflow-root>`

## Reports format (MVP)
- Naming:
  - Research context: `aidd/reports/research/<ticket>-context.json` + `*.pack.yaml|*.pack.toon`
  - Research targets: `aidd/reports/research/<ticket>-targets.json`
  - QA: `aidd/reports/qa/<ticket>.json` + pack
  - PRD review: `aidd/reports/prd/<ticket>.json` + pack
  - Reviewer marker: `aidd/reports/reviewer/<ticket>.json`
  - Tests log: `aidd/reports/tests/<ticket>.jsonl`
- Pack‑first: читать pack (yaml/toon) если есть, иначе JSON.
- Header (минимум): `schema`, `pack_version`, `type`, `kind`, `ticket`, `slug|slug_hint`, `generated_at`, `status`, `summary` (если есть), `tests_summary` (QA), `source_path`.
- Determinism: стабильная сериализация, stable‑truncation, стабильные `id`.
- Columnar формат: `cols` + `rows`.
- Budgets (пример):
  - research context pack: total <= 1200 chars, matches<=20, reuse<=8, call_graph<=30
  - QA pack: findings<=20, tests_executed<=10
  - PRD pack: findings<=20, action_items<=10
- Патчи (опционально): RFC6902 в `aidd/reports/<type>/<ticket>.patch.json`.
- Pack‑only/field filters: `AIDD_PACK_ONLY`, `AIDD_PACK_ALLOW_FIELDS`, `AIDD_PACK_STRIP_FIELDS`.
- Pack‑env: `AIDD_PACK_FORMAT`, `AIDD_PACK_LIMITS`, `AIDD_PACK_ENFORCE_BUDGET`.

## Release checklist (сжато)
- Обновить `README.md`/`README.en.md` и `AGENTS.md` при изменении поведения.
- Закрыть задачи в `backlog.md`, создать следующую волну при необходимости.
- Прогнать `tests/repo_tools/ci-lint.sh` и `tests/repo_tools/smoke-workflow.sh`.
- Проверить prompt‑versioning и prompt‑lint (см. выше).
- Убедиться, что dev‑only артефакты не попали в дистрибутив.
- Обновить `CHANGELOG.md` (и release notes при необходимости).

## ADR: Workspace в `aidd/`
- Решение: рабочие артефакты живут в `./aidd`, плагин — в корне репозитория.
- Init идемпотентен и не перезаписывает пользовательские файлы.
- Smoke/pytest используют текущий git checkout.

## Prompt templates

### Agent template
```md
---
name: {{NAME}}
description: {{DESCRIPTION}}
lang: {{LANG}}
prompt_version: {{PROMPT_VERSION}}
source_version: {{SOURCE_VERSION}}
tools: {{TOOLS}}
model: inherit
---

## Контекст
Кратко опишите роль агента, его цель и ключевые ограничения. Ссылайтесь на документы формата `@aidd/docs/...`. Подчеркните agent-first подход: какие данные агент обязан собрать сам и какие команды он запускает до обращения к пользователю.

## Входные артефакты
- `aidd/docs/prd/<ticket>.prd.md` — пример обязательного входа. Укажите, какие файлы требуются и что делать, если их нет.
- Перечислите остальные артефакты (plan, tasklist, отчёты, `aidd/reports/*.json`) и отметьте условия (READY/BLOCKED). Обязательно опишите, как агент ищет ссылки (например, `rg <ticket> aidd/docs/**`, поиск по ADR, использование slug-hint из `aidd/docs/.active_feature`).

## Автоматизация
- Перечислите гейты (`gate-*`), хуки и переменные (`SKIP_AUTO_TESTS`, `TEST_SCOPE`), которые агент обязан учитывать.
- Укажите разрешённые CLI-команды (`<test-runner> …`, `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh …`, `rg …`) и как агент должен логировать вывод/пути. Опишите, как реагировать на автозапуск `${CLAUDE_PLUGIN_ROOT}/hooks/format-and-test.sh` и когда использовать ручные команды.

## Пошаговый план
1. Распишите действия агента (чтение артефактов, запуск `rg`/`<test-runner>`, обновление файлов, обращение к другим агентам).
2. Каждое действие должно приводить к измеримому результату (например, обновлённый файл, лог команды, ссылка на отчёт).
3. Укажите, что вопросы пользователю допустимы только после перечисления проверенных артефактов и должны включать формат ответа.

## Fail-fast и вопросы
- Укажите условия, при которых агент должен остановиться и запросить данные у пользователя (например, отсутствует PRD/plan). Перед вопросом перечислите, что уже проверено.
- Формат вопросов:
  ```
  Вопрос N (Blocker|Clarification): ...
  Зачем: ...
  Варианты: A) ... B) ...
  Default: ...
  ```

## Формат ответа
- Всегда начинайте с `Checkbox updated: ...`.
- Далее укажите `Status: ...`, `Artifacts updated: ...`, `Next actions: ...` и ссылки на файлы/команды.
- Если статус BLOCKED, перечислите конкретные вопросы, список проверенных артефактов и следующие шаги.
```

### Command template
```md
---
description: {{DESCRIPTION}}
argument-hint: {{ARGUMENT_HINT}}
lang: {{LANG}}
prompt_version: {{PROMPT_VERSION}}
source_version: {{SOURCE_VERSION}}
allowed-tools: {{ALLOWED_TOOLS}}
model: inherit
---

## Контекст
Опишите назначение команды, связь с агентами и обязательные предварительные условия (активный ticket, готовые артефакты и т.д.). Уточните, что команда следует agent-first принципам: собирает данные из репозитория и запускает разрешённые CLI автоматически, а вопросы пользователю задаёт только при отсутствии информации.

## Входные артефакты
- Перечислите файлы/репорты (`aidd/docs/prd/*.md`, `aidd/docs/research/*.md`, `aidd/reports/*.json`, slug-hint в `aidd/docs/.active_feature`) и укажите, как команда находит их (например, `rg <ticket>`).
- Отметьте, что делать при отсутствии входа (остановиться с BLOCKED, попросить запустить другую команду) и какие команды нужно выполнить, прежде чем просить пользователя о данных.

## Когда запускать
- Опишите стадии workflow, в которых команда применяется, и кто инициирует запуск.
- Уточните ограничения (например, только после `/feature-dev-aidd:review-spec` или при статусе READY).

## Автоматические хуки и переменные
- Перечислите хуки/гейты и команды, запускаемые во время выполнения (`${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh`, `${CLAUDE_PLUGIN_ROOT}/tools/research.sh`, `${CLAUDE_PLUGIN_ROOT}/hooks/format-and-test.sh`, `<test-runner> <args>`, `rg`).
- Опишите переменные окружения (`SKIP_AUTO_TESTS`, `FORMAT_ONLY`, `TEST_SCOPE`) и требования к логам/ссылкам на вывод команд.

## Что редактируется
- Укажите файлы/директории, которые команда должна обновлять (например, `aidd/docs/tasklist/<ticket>.md`, `src/**`), и какие артефакты нужно ссылать в ответе (diff, отчёты, логи команд).
- Добавьте ссылки на шаблоны и требования к структуре правок, включая хранение команд и источников данных.

## Пошаговый план
1. Распишите последовательность действий команды (вызов саб-агентов, запуск скриптов, обновление артефактов).
2. Добавьте проверки готовности (например, `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source ...`).
3. При необходимости предусмотрите ветки для ручных вмешательств.

## Fail-fast и вопросы
- Опишите ситуации, когда команда должна остановиться (нет PRD, отсутствует approved статус, не найден список задач).
- Формат вопросов:
  ```
  Вопрос N (Blocker|Clarification): ...
  Зачем: ...
  Варианты: A) ... B) ...
  Default: ...
  ```

## Ожидаемый вывод
- Укажите, какие файлы/разделы должны быть обновлены по завершении.
- Зафиксируйте требования к финальному сообщению: `Checkbox updated: ...`, затем `Status: ...`, `Artifacts updated: ...`, `Next actions: ...`.

## Примеры CLI
- Приведите пример вызова команды/скрипта (например, `/feature-dev-aidd:implement ABC-123` или `!bash -lc '${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh --source qa --ticket ABC-123'`).
- Добавьте подсказки по аргументам и типовым ошибкам.
```
