# Claude Code Workflow — Language-agnostic Workflow Template

> Готовый GitHub-шаблон и инсталлятор, который подключает Claude Code к репозиторию любого стека, добавляет слэш-команды, безопасные хуки, stage-aware гейты и настраиваемые проверки (форматирование/тесты/линтеры).

## TL;DR
- `claude-workflow init --target .` (или `aidd/init-claude-workflow.sh` из payload) разворачивает цикл `/idea-new (analyst) → research при необходимости → /plan-new → /review-spec (review-plan + review-prd) → /tasks-new → /implement → /review → /qa`; `claude-workflow preset|sync|upgrade|smoke` покрывают демо-артефакты, обновление payload и e2e-smoke.
- Автоформат и выборочные проверки (`aidd/hooks/format-and-test.sh`) запускаются только на стадии `implement` и только на Stop/SubagentStop (`SKIP_AUTO_TESTS=1` временно отключает); артефакты защищены хуками `gate-*`.
- Стадия фичи хранится в `aidd/docs/.active_stage` и обновляется слэш-командами (`/idea-new`, `/plan-new`, `/review-spec`, `/tasks-new`, `/implement`, `/review`, `/qa`); можно откатываться к любому этапу.
- Настраиваемые режимы веток/коммитов через `config/conventions.json` и готовые шаблоны документации/промптов.
- Опциональные интеграции с GitHub Actions, Issue/PR шаблонами и политиками доступа Claude Code.
- Payload ставится в поддиректорию `aidd/` (`aidd/agents`, `aidd/commands`, `aidd/hooks`, `aidd/.claude-plugin`, `aidd/docs`, `aidd/config`, `aidd/claude-presets`, `aidd/templates`, `aidd/tools`, `aidd/scripts`, `aidd/prompts`); все артефакты и отчёты (`aidd/reports/**`) живут там же. Workspace‑настройки лежат в корне (`.claude/settings.json`, `.claude/cache/`, `.claude-plugin/marketplace.json`) — запускайте CLI с `--target .` или из `aidd/`, если команды не видят файлы.
  Корневые служебные файлы — только `.claude/` и `.claude-plugin/`, все остальные артефакты берутся из payload `aidd/`.
- **Troubleshooting путей:** все артефакты (PRD/Research/QA/PRD Review/Reviewer) находятся под `aidd/`. Если `Read(reports/...)` не находит файл, проверяйте `aidd/reports/...` и запускайте CLI с `${CLAUDE_PLUGIN_ROOT:-./aidd}` или `--target aidd`.

## Оглавление
- [CLI шпаргалка](#cli-шпаргалка)
- [Что входит в шаблон](#что-входит-в-шаблон)
- [Архитектура workflow](#архитектура-workflow)
- [Agent-first принципы](#agent-first-принципы)
- [Структура репозитория](#структура-репозитория)
- [Состав репозитория](#состав-репозитория)
- [Детальный анализ компонентов](#детальный-анализ-компонентов)
- [Архитектура и взаимосвязи](#архитектура-и-взаимосвязи)
- [Ключевые скрипты и хуки](#ключевые-скрипты-и-хуки)
- [Тестовый контур](#тестовый-контур)
- [Диагностика и отладка](#диагностика-и-отладка)
- [Политики доступа и гейты](#политики-доступа-и-гейты)
- [Документация и шаблоны](#документация-и-шаблоны)
- [Примеры и демо](#примеры-и-демо)
- [Незакрытые задачи и наблюдения](#незакрытые-задачи-и-наблюдения)
- [Установка](#установка)
  - [Вариант A — `uv tool install` (рекомендуется)](#вариант-a--uv-tool-install-рекомендуется)
  - [Вариант B — `pipx`](#вариант-b--pipx)
  - [Вариант C — локально (bash-скрипт)](#вариант-c--локально-bash-скрипт)
- [Предпосылки](#предпосылки)
- [Быстрый старт в Claude Code](#быстрый-старт-в-claude-code)
- [Чеклист запуска фичи](#чеклист-запуска-фичи)
- [Слэш-команды](#слэш-команды)
- [Режимы веток и коммитов](#режимы-веток-и-коммитов)
- [Выборочные тесты](#выборочные-тесты)
- [Дополнительно](#дополнительно)
- [Миграция на agent-first](#миграция-на-agent-first)
- [Вклад и лицензия](#вклад-и-лицензия)

## CLI шпаргалка
- `claude-workflow init --target . [--commit-mode ... --enable-ci --prompt-locale en]` — bootstrap в `./aidd`.
- `claude-workflow preset feature-prd|feature-plan|feature-impl|feature-design|feature-release --ticket demo` — разложить демо-артефакты.
- `claude-workflow sync --include .claude --include .claude-plugin [--include claude-presets --release latest]` / `claude-workflow upgrade [--force]` — подтянуть обновления payload (без перезаписи изменённых файлов, кроме `--force`).
- `claude-workflow smoke` — e2e-smoke idea → plan → review-spec (review-plan + review-prd) → tasklist + гейты.
- `claude-workflow analyst-check --ticket <ticket>` — валидация диалога analyst и статуса PRD.
- `claude-workflow research --ticket <ticket> --auto --deep-code [--call-graph]` — сбор целей/матчей/графа вызовов.
- `claude-workflow reviewer-tests --status required|optional --ticket <ticket>` — маркер автотестов на ревью.
- `claude-workflow tasks-derive --source qa|review|research --append --ticket <ticket>` — handoff-задачи в `aidd/docs/tasklist/<ticket>.md`.
- `claude-workflow qa --ticket <ticket> --gate` — отчёт QA + гейт.
- `claude-workflow progress --source implement|qa|review|handoff --ticket <ticket>` — подтверждение новых `- [x]`/handoff-пунктов.

## Что входит в шаблон
- Слэш-команды Claude Code и саб-агенты для подготовки PRD/ADR/Tasklist, генерации документации и валидации коммитов.
- Многошаговый workflow (идея → research → план → review-plan → review-prd → задачи → реализация → ревью → QA; можно одной командой `/review-spec`) с саб-агентами `analyst/planner/plan-reviewer/prd-reviewer/validator/implementer/reviewer/qa`; дополнительные проверки включаются через `config/gates.json`.
- Git-хуки для автоформатирования, выборочных тестов и workflow-гейтов (стадии учитываются автоматически).
- Конфигурация коммитов (`ticket-prefix`, `conventional`, `mixed`) и вспомогательные скрипты CLI.
- Базовый набор документации, issue/PR шаблонов и CI workflow (включается флагом `--enable-ci`).
- Локальная, прозрачная установка без зависимости от Spec Kit или BMAD.

## Архитектура workflow
1. `claude-workflow init --target .` (или `aidd/init-claude-workflow.sh` из payload) разворачивает workspace‑настройки `.claude/` и `.claude-plugin/`, а payload — в `aidd/` (команды/агенты/хуки/доки/скрипты).
2. Slash-команды Claude Code запускают многошаговый процесс (см. `aidd/workflow.md`): от идеи и плана до реализации и ревью, подключая специализированных саб-агентов.
3. Плагин `feature-dev-aidd` из `.claude-plugin/marketplace.json` вешает pre-/post-хуки (`gate-*`, `format-and-test.sh`); `.claude/settings.json` хранит только разрешения/automation и включает плагин.
4. Хук `format-and-test.sh` выполняет форматирование и выборочные тесты через `automation` в `.claude/settings.json`, и работает только на стадии `implement` (Stop/SubagentStop).
5. Политики доступа и режимы веток/коммитов управляются через `.claude/settings.json` и `config/conventions.json`.

Детали настройки и расширения описаны в `aidd/workflow.md` и `aidd/docs/customization.md`.

## Agent-first принципы
- **Сначала slug-hint и артефакты, затем вопросы.** Аналитик начинает со `aidd/docs/.active_feature` (пользовательский slug-hint), затем читает `aidd/docs/research/<ticket>.md`, `reports/research/*.json` (включая `code_index`/`reuse_candidates`), существующие планы/ADR и только потом формирует Q&A для пробелов. Исследователь фиксирует каждую команду (`claude-workflow research --auto --deep-code`, `rg "<ticket>" src/**`, `find`, `python`) и строит call/import graph Claude Code'ом, а implementer обновляет tasklist и перечисляет запущенные команды тестов/линтеров и `claude-workflow progress` перед тем как обращаться к пользователю.
- **Команды и логи — часть ответа.** Все промпты и шаблоны требуют указывать разрешённые CLI (например, ваш тест‑раннер, `rg`, `claude-workflow`) и прикладывать вывод/пути, чтобы downstream-агенты могли воспроизвести шаги. Tasklist и research-шаблон теперь содержат разделы «Commands/Reports».
- **Автогенерация артефактов.** `/idea-new` автоматически создаёт PRD, обновляет отчёты Researcher и инструктирует аналитика собирать данные из репозитория. Пресеты `templates/prompt-agent.md` и `templates/prompt-command.md` подсказывают, как описывать входы, гейты, команды и fail-fast блоки в стиле agent-first.

## Структура репозитория
| Каталог/файл | Назначение | Ключевые детали |
| --- | --- | --- |
| `.claude/settings.json` | Политики доступа и автоматизации | Пресеты `start`/`strict`, allow/ask/deny, automation; pre/post-хуки живут в плагине (`hooks/hooks.json`) |
| `aidd/commands/` | Инструкция для слэш-команд | Маршруты `/idea-new`, `/researcher`, `/plan-new`, `/review-spec`, `/tasks-new`, `/implement`, `/review`, `/qa` с `allowed-tools` и встроенными shell-шагами |
| `aidd/agents/` | Playbook саб-агентов | Роли `analyst`, `planner`, `plan-reviewer`, `prd-reviewer`, `validator`, `implementer`, `reviewer`, `qa` |
| `aidd/prompts/en/` | EN-версии промптов | `aidd/prompts/en/agents/*.md`, `aidd/prompts/en/commands/*.md`, синхронизированы с `aidd/agents|commands` (см. `aidd/docs/prompt-versioning.md`) |
| `aidd/hooks/` | Защитные и утилитарные хуки | `gate-workflow.sh`, `gate-prd-review.sh`, `gate-tests.sh`, `gate-qa.sh`, `lint-deps.sh`, `format-and-test.sh` |
| `aidd/scripts/` | Runtime-скрипты | Контекстные хелперы, агентские скрипты и опциональные помощники для тест-раннера |
| `config/gates.json` | Параметры гейтов | Управляет `prd_review`, `tests_required`, `deps_allowlist`, `qa`, `feature_ticket_source`, `feature_slug_hint_source` (использует `aidd/docs/.active_*`) |
| `config/conventions.json` | Режимы веток и коммитов | Расписаны шаблоны `ticket-prefix`, `conventional`, `mixed`, правила ветвления и ревью |
| `config/allowed-deps.txt` | Allowlist зависимостей | Формат `group:artifact`; предупреждения выводит `lint-deps.sh` |
| `aidd/docs/` | Руководства и шаблоны | `customization.md`, `agents-playbook.md`, `qa-playbook.md`, `feature-cookbook.md`, `release-notes.md`, шаблоны PRD/ADR/tasklist, рабочие артефакты фич |
| `examples/` | Демо-материалы | Сценарий `apply-demo.sh` и базовые примеры структуры |
| `scripts/` | CLI и вспомогательные сценарии | `ci-lint.sh` (линтеры + тесты), `smoke-workflow.sh` (E2E smoke сценарий gate-workflow), `prd-review-agent.py` (эвристика ревью PRD), `qa-agent.py` (эвристический QA-агент), `bootstrap-local.sh` (локальное dogfooding payload) |
| `templates/` | Шаблоны вендорных артефактов | Git-хуки (`commit-msg`, `pre-push`, `prepare-commit-msg`) и расширенный шаблон `aidd/docs/tasklist/<ticket>.md` |
| `tests/` | Python-юнит-тесты | Проверяют init-скрипт, хуки, selective tests и настройки доступа |
| `.github/workflows/ci.yml` | CI pipeline | Запускает `scripts/ci-lint.sh`, ставит `shellcheck`, `markdownlint`, `yamllint` |
| `aidd/init-claude-workflow.sh` | Bootstrap-скрипт | Флаги `--commit-mode`, `--enable-ci`, `--force`, `--dry-run`, проверка зависимостей и генерация структуры |
| `aidd/workflow.md` | Процессная документация | Детальный сценарий idea → research → plan → review-plan → review-prd → tasks → implement → review → qa (доступен `/review-spec`) |
| `claude-workflow-extensions.patch` | Пакет расширений | Diff с дополнительными агентами, гейтами и командами для продвинутых установок |
| `README.en.md` | Англоязычный README | Синхронизируется с этой версией, содержит пометку _Last sync_ |
| `CONTRIBUTING.md` | Правила вкладов | Описывает процесс PR/issue, требования к коммитам и линтингу |
| `LICENSE` | Лицензия | MIT с ограничениями ответственности |

## Состав репозитория
- **Runtime (у пользователя):** `aidd/**` + корневые `.claude/` и `.claude-plugin/` после `claude-workflow init`.
- **Dev-only (в этом репозитории):** `doc/dev/`, `tests/`, `examples/`, `tools/`, `scripts/`, `.github/`, `.dev/`, `.tmp-debug/`, `build/` — не входят в payload.
- **Где смотреть документацию:** user-facing гайды живут в `aidd/docs/**`, dev‑планирование — в `doc/dev/`.

> `aidd/init-claude-workflow.sh` разворачивает `aidd/hooks/*` и документацию. Ветки и сообщения коммитов настраиваются стандартными git-командами по правилам `config/conventions.json`.

## Детальный анализ компонентов

### Скрипты установки и утилиты
- `aidd/init-claude-workflow.sh` — модульный bootstrap со строгими проверками (`bash/git/python3`), режимами `--commit-mode/--enable-ci/--force/--dry-run` и потоковой синхронизацией артефактов из `src/claude_workflow_cli/data/payload/` (без heredoc-вставок), включая обновление `config/conventions.json`.
- `scripts/ci-lint.sh` — единая точка для `shellcheck`, `markdownlint`, `yamllint` и `python -m unittest`, интегрированная с CI и корректно пропускающая отсутствующие линтеры с предупреждением.
- `scripts/smoke-workflow.sh` — E2E smoke-сценарий: поднимает временный проект, запускает bootstrap, воспроизводит ticket-first цикл (`ticket → PRD → план → review-spec → tasklist`) и проверяет, что `gate-workflow.sh`/`tasklist_progress` блокируют правки без новых `- [x]`.
- `scripts/bootstrap-local.sh` — копирует `src/claude_workflow_cli/data/payload/` в `.dev/.claude-example/` (workspace по умолчанию; workflow всегда в поддиректории `aidd/`) для быстрой проверки payload без публикации новой версии CLI.
- `claude-workflow sync` / `claude-workflow upgrade` — поддерживают режим `--release <tag|owner/repo@tag|latest>` для скачивания payload из GitHub Releases (кешируется в `~/.cache/claude-workflow`, переопределяется `--cache-dir` или `CLAUDE_WORKFLOW_CACHE`). CLI сверяет контрольные суммы из `manifest.json`, перед синхронизацией выводит diff и при недоступности сети откатывается к встроенному payload.
- `examples/apply-demo.sh` — демонстрирует применение шаблона к демо-проекту, печатает дерево каталогов до/после и запускает проверки, если они настроены.

### Git-хуки и автоматизация
- `aidd/hooks/format-and-test.sh` — Python-хук, который читает `.claude/settings.json`, учитывает `SKIP_FORMAT`, `FORMAT_ONLY`, `TEST_SCOPE`, `STRICT_TESTS`, `SKIP_AUTO_TESTS`, анализирует `git diff`, активный ticket (и slug-хинт) из `aidd/docs/.active_ticket`/`.active_feature`, умеет переключать selective/full run и подбирает задачи через `moduleMatrix`, `defaultTasks`, `fallbackTasks`. Запускается на Stop/SubagentStop и только при стадии `implement`.
- `aidd/hooks/gate-workflow.sh` — блокирует правки под `src/**`, если для активного ticket нет PRD, плана или новых `- [x]` в `aidd/docs/tasklist/<ticket>.md` (гейт `tasklist_progress`), игнорирует изменения в документации/шаблонах.
- `aidd/hooks/gate-tests.sh` — опциональная проверка из `config/gates.json`: контролирует наличие сопутствующих тестов (`disabled|soft|hard`), по умолчанию игнорирует тестовые директории (`exclude_dirs`), выводит подсказки по разблокировке.
- `aidd/hooks/gate-qa.sh` — вызывает `scripts/qa-agent.py`, формирует `reports/qa/<ticket>.json`, маркирует `blocker/critical` как блокирующие; см. `aidd/docs/qa-playbook.md`.
- `aidd/hooks/lint-deps.sh` — отслеживает изменения зависимостей, сверяет их с allowlist `config/allowed-deps.txt` и сигнализирует при расхождениях.

### Саб-агенты Claude Code
- `aidd/agents/analyst.md` — формализует идею в PRD со статусом READY/BLOCKED, задаёт уточняющие вопросы, фиксирует риски/допущения и обновляет `aidd/docs/prd/<ticket>.prd.md`.
- `aidd/agents/planner.md` — строит пошаговый план (`aidd/docs/plan/<ticket>.md`) с DoD и зависимостями; `aidd/agents/validator.md` проверяет план и записывает вопросы для продуктов/архитекторов.
- `aidd/agents/implementer.md` — ведёт реализацию малыми итерациями, отслеживает гейты, обновляет чеклист (`Checkbox updated: …`, передаёт новые `- [x]`) и вызывает `claude-workflow progress --source implement`.
- `aidd/agents/reviewer.md` — оформляет код-ревью, проверяет чеклисты, ставит статусы READY/BLOCKED, фиксирует follow-up в `aidd/docs/tasklist/<ticket>.md` и запускает `claude-workflow progress --source review`.
- `aidd/agents/qa.md` — финальная QA-проверка; готовит отчёт с severity, обновляет `aidd/docs/tasklist/<ticket>.md`, запускает `claude-workflow progress --source qa` и взаимодействует с `gate-qa.sh`.

### Слэш-команды и пайплайн
- Ветки создайте `git checkout -b feature/<TICKET>` или по другим паттернам из `config/conventions.json`.
- `aidd/commands/idea-new.md` — фиксирует ticket (и при необходимости slug-хинт) в `aidd/docs/.active_ticket`/`.active_feature`, запускает `analyst` (research — по требованию), **создаёт черновик `aidd/docs/prd/<ticket>.prd.md` (Status: draft)** и открытые вопросы.
- `aidd/commands/researcher.md` — собирает контекст (CLI `claude-workflow research`) и оформляет отчёт `aidd/docs/research/<ticket>.md`.
- `aidd/commands/plan-new.md` — подключает `planner` и `validator`, обновляет план и протокол проверки.
- `aidd/commands/tasks-new.md` — синхронизирует `aidd/docs/tasklist/<ticket>.md` с планом, распределяя задачи по этапам и заполняя slug-хинт/артефакты.
- `aidd/commands/implement.md` — фиксирует шаги реализации, напоминает про гейты и автоматические тесты.
- `aidd/commands/review.md` — оформляет ревью, обновляет чеклисты и статус READY/BLOCKED.
- Сообщения коммитов формируйте вручную (`git commit`), сверяясь со схемами в `config/conventions.json`.

### Конфигурация и политики
- `.claude/settings.json` — пресеты `start/strict`, списки `allow/ask/deny` и параметры `automation` (формат/тесты); pre/post-хуки поставляет плагин.
- `config/conventions.json` — commit/branch режимы (`ticket-prefix`, `conventional`, `mixed`), шаблоны сообщений, примеры, заметки для ревью и CLI.
- `config/gates.json` — флаги `tests_required`, `deps_allowlist`, `qa`, `feature_ticket_source`, `feature_slug_hint_source`; управляет поведением гейтов и `lint-deps.sh`.
- `config/allowed-deps.txt` — allowlist `group:artifact`, поддерживает комментарии, используется `lint-deps.sh`.

### Документация и шаблоны
- `aidd/workflow.md`, `aidd/docs/customization.md`, `aidd/docs/agents-playbook.md` — описывают процесс idea→research→review, walkthrough установки, настройку `.claude/settings.json` и роли саб-агентов.
- `aidd/docs/prd.template.md`, `aidd/docs/adr.template.md`, `aidd/docs/tasklist.template.md`, `templates/tasklist.md` — шаблоны с подсказками, чеклистами, секциями истории изменений и примерами заполнения.
- `templates/git-hooks/*.sample`, `templates/git-hooks/README.md` — готовые `commit-msg`, `prepare-commit-msg`, `pre-push` с инструкциями, переменными окружения и советами по развёртыванию.
- `aidd/docs/release-notes.md` — регламент релизов и checklist обновлений (используется для планирования roadmap и changelog).

### Тесты и контроль качества
- `tests/helpers.py` — утилиты: генерация файлов, git init/config, создание `config/gates.json`, запуск хуков.
- `tests/test_init_claude_workflow.py` — проверка bootstrap-скрипта, флагов `--dry-run`, `--force`, наличия ключевых артефактов.
- `tests/test_gate_*.py` — сценарии для гейтов workflow, API, миграций БД, обязательных тестов; учитывают tracked/untracked миграции и пропуски нецелевых файлов.
- `tests/test_format_and_test.py` — покрытие selective runner: `moduleMatrix`, общие файлы, переменные `TEST_SCOPE`, `SKIP_AUTO_TESTS`.
- `tests/test_settings_policy.py` — проверяет, что `permissions` настроены безопасно и хуки берутся из плагина (не дублируются в settings).
- `tools/payload_audit.py` — аудит состава payload по allowlist/denylist (защита от случайных dev-only файлов в дистрибутиве).

### Демо и расширения
- `examples/` — опциональные демо-проекты и сценарии.
- `claude-workflow-extensions.patch` — patch-файл с расширениями агентов, команд и гейтов, готовый к применению на чистый репозиторий.

## Архитектура и взаимосвязи
- Инициализация (`aidd/init-claude-workflow.sh`) генерирует `.claude/settings.json`, `.claude-plugin/marketplace.json` и раскладывает payload в `aidd/`; хуки подключает плагин `feature-dev-aidd`.
- Pre-/post-хуки (`gate-*`, `format-and-test.sh`, `lint-deps.sh`) перечислены в `aidd/hooks/hooks.json` и ссылаются на `${CLAUDE_PLUGIN_ROOT}/hooks/*` (основные проверки запускаются на Stop/SubagentStop).
- Гейты (`gate-*`) читают `config/gates.json` и артефакты в `aidd/docs/**`, обеспечивая прохождение цепочки `/idea-new → research (при необходимости) → /plan-new → /review-spec → /tasks-new`; дополнительные проверки (`researcher`, `prd_review`, `tests_required`) включаются по мере необходимости.
- Стадии фиксируются в `aidd/docs/.active_stage`: `format-and-test`, `gate-tests`, `lint-deps` активны только при `implement`, `gate-qa` — только при `qa`, а `gate-workflow` ограничивает правки кода вне `implement/review/qa` (если стадия задана).
- Тестовый набор на Python использует `tests/helpers.py` для эмуляции git/файловой системы, покрывая dry-run, tracked/untracked изменения и поведение хуков.

## Ключевые скрипты и хуки
- **`aidd/init-claude-workflow.sh`** — валидирует `bash/git/python3`, генерирует `.claude/`, `.claude-plugin/` и `aidd/**`, перезаписывает артефакты по `--force`, выводит dry-run и настраивает режим коммитов.
- **`aidd/hooks/format-and-test.sh`** — анализирует `git diff`, собирает задачи из `automation.tests` (`changedOnly`, `moduleMatrix`), уважает `SKIP_FORMAT`, `FORMAT_ONLY`, `TEST_SCOPE`, `STRICT_TESTS`, `SKIP_AUTO_TESTS` и умеет подстраивать полный прогон при изменении общих файлов; запускается на стадии `implement`.
- **`gate-prd-review.sh`** — вызывает `scripts/prd_review_gate.py`, который требует наличие `aidd/docs/prd/<ticket>.prd.md`, секции `## PRD Review` со статусом из `approved_statuses`, закрытые action items и JSON-отчёт (`reports/prd/<ticket>.json` по умолчанию); блокирующие статусы, `- [ ]` и findings с severity из `blocking_severities` завершают проверку ошибкой, а флаги `skip_branches`, `allow_missing_section`, `allow_missing_report` и шаблон `report_path` задаются в `config/gates.json`.
- **`gate-workflow.sh`** — блокирует изменения в `src/**`, пока не создана цепочка PRD/план/tasklist для активной фичи (`aidd/docs/.active_ticket`) и не появилось новых `- [x]` в `aidd/docs/tasklist/<ticket>.md`.
- **`gate-tests.sh`** — опциональный гейт: при включении проверяет наличие тестов для изменённых исходников (режимы задаёт `config/gates.json`), игнорирует тестовые каталоги через `exclude_dirs`.
- **`lint-deps.sh`** — напоминает про allowlist зависимостей из `config/allowed-deps.txt` и анализирует изменения манифестов/конфигов зависимостей.
- **`scripts/ci-lint.sh`** — единая точка для `shellcheck`, `markdownlint`, `yamllint` и `python -m unittest`, используется локально и в GitHub Actions.
- **`scripts/smoke-workflow.sh`** — поднимает временной проект, гоняет init-скрипт и проверяет прохождение `gate-workflow` по шагам `/idea-new → /plan-new → /review-spec → /tasks-new`.
- **`examples/apply-demo.sh`** — пошагово применяет шаблон к демо-проекту и показывает, как проходит bootstrap.
- **`scripts/prompt-release.sh`** — автоматизирует bump версий промптов (`scripts/prompt-version`), линтер, pytest-наборы и проверку payload/gate перед подготовкой релиза.
- **`scripts/scaffold_prompt.py`** — разворачивает шаблоны `templates/prompt-agent.md` / `templates/prompt-command.md`, подставляет фронт-маттер и создаёт новые промпты (`--type agent|command`, `--target ...`, `--force`).

## Тестовый контур
- `tests/helpers.py` — вспомогательные функции (создание файлов, git init/config, запуск хуков) для изоляции сценариев.
- `tests/test_init_claude_workflow.py` — проверяет чистую установку, `--dry-run`, `--force`, наличие ключевых артефактов и поведение bootstrap-скрипта.
- `tests/test_gate_*.py` — проверяют workflow/API/DB/tests гейты: учитывают ticket/slug-хинт, tracked/untracked миграции, режимы `soft/hard/disabled` и нецелевые файлы.
- `tests/test_format_and_test.py` — моделирует запуск Python-хука, проверяет `moduleMatrix`, реакцию на общие файлы, переменные `SKIP_AUTO_TESTS`, `TEST_SCOPE`.
- `tests/test_settings_policy.py` — валидирует `.claude/settings.json`, гарантируя, что критичные команды (`git add/commit/push`, `curl`, запись в прод-пути) находятся в `ask/deny` и хуки остаются в плагине (не дублируются в settings).
- `scripts/ci-lint.sh` и `.github/workflows/ci.yml` — единый entrypoint линтеров/тестов для локального запуска и GitHub Actions.
- `scripts/smoke-workflow.sh` — E2E smoke, подтверждает, что `gate-workflow` блокирует исходники до появления PRD/плана/review-plan/PRD review/tasklist (`aidd/docs/tasklist/<ticket>.md`); для ревью используйте `/review-spec`.

## Диагностика и отладка
- **Линтеры и тесты:** запускайте `scripts/ci-lint.sh` для полного набора (`shellcheck`, `markdownlint`, `yamllint`, `python -m unittest`) или адресно `python3 -m unittest tests/test_gate_workflow.py`.
- **Переменные окружения:** `SKIP_AUTO_TESTS`, `SKIP_FORMAT`, `FORMAT_ONLY`, `TEST_SCOPE`, `TEST_CHANGED_ONLY`, `STRICT_TESTS` управляют `aidd/hooks/format-and-test.sh`.
- **Диагностика гейтов:** передайте payload через stdin: `echo '{"tool_input":{"file_path":"src/app.py"}}' | CLAUDE_PROJECT_DIR=$PWD aidd/hooks/gate-workflow.sh`.
- **Selective runner:** настройте `automation.tests.moduleMatrix` в `.claude/settings.json`, чтобы сопоставлять пути и команды тест‑раннера; для отладки включайте `TEST_SCOPE` и `TEST_CHANGED_ONLY=0`.
- **Smoke-сценарий:** `scripts/smoke-workflow.sh` поднимет временной проект и проверит последовательность `/idea-new → /plan-new → /review-spec → /tasks-new`.
- **CI-проверки:** GitHub Actions (`.github/workflows/ci.yml`) ожидает установленные `shellcheck`, `yamllint`, `markdownlint`; убедитесь, что локальная среда воспроизводит их версии при отладке.

## Политики доступа и гейты
- `.claude/settings.json` содержит пресеты `start` и `strict`: первый позволяет базовые операции, второй расширяет allow/ask/deny; хуки подключает плагин `feature-dev-aidd` (`hooks/hooks.json`).
- Раздел `automation` управляет форматированием и тестами; настройте `format`/`tests` под ваш тест‑раннер.
- `config/gates.json` централизует флаги `prd_review`, `tests_required`, `deps_allowlist`, а также пути к активному ticket (`feature_ticket_source`) и slug-хинту (`feature_slug_hint_source`); для `prd_review` доступны параметры `approved_statuses`, `blocking_statuses`, `blocking_severities`, `allow_missing_section`, `allow_missing_report`, `report_path`, `skip_branches` и `branches`.
- `aidd/docs/.active_stage` задаёт текущую стадию и ограничивает выполнение гейтов (implement/review/qa); для ручного обхода используйте `CLAUDE_SKIP_STAGE_CHECKS=1` или `CLAUDE_ACTIVE_STAGE`.
- Комбинация хуков `gate-*` в `aidd/hooks/` (вызываются через plugin hooks/hooks.json) реализует согласованную политику: блокировка кода без артефактов, требование миграций и тестов, контроль API-контрактов.

## Документация и шаблоны
- `aidd/workflow.md`, `aidd/docs/agents-playbook.md` — описывают целевой цикл idea→review, роли саб-агентов и взаимодействие с гейтами.
- `aidd/workflow.md`, `aidd/docs/customization.md` — walkthrough применения bootstrap и подробности настройки `.claude/settings.json`, гейтов, шаблонов команд.
- `aidd/docs/release-notes.md` — регламент релизов и планирование roadmap.
- `aidd/docs/prompt-playbook.md` — единые правила оформления промптов агентов/команд (обязательные секции, `Checkbox updated`, Fail-fast, ссылки на артефакты и матрица ролей).
- `aidd/docs/prompt-versioning.md` — политика двуязычных промптов, правила `prompt_version`, `Lang-Parity: skip`, скрипты `prompt-version` и `prompt_diff`.
- `templates/prompt-agent.md`, `templates/prompt-command.md`, `claude-presets/advanced/prompt-governance.yaml` — шаблоны и пресет для генерации новых промптов; используйте вместе со скриптом `scripts/scaffold_prompt.py`.
- Шаблоны PRD/ADR/tasklist (`aidd/docs/*.template.md`, `templates/tasklist.md`) и git-хуки (`templates/git-hooks/*.sample`) — расширенные заготовки с подсказками, чеклистами и переменными окружения.
- `README.en.md` — синхронизированный перевод; при правках обновляйте обе версии и поле Last sync.

## Примеры и демо
- `examples/` — опциональные демо‑проекты (можно удалить без влияния на workflow).
- `examples/apply-demo.sh` — пошаговый сценарий применения bootstrap к демо-проекту, полезен для воркшопов и презентаций.
- `scripts/smoke-workflow.sh` + `aidd/workflow.md` — живой пример: скрипт автоматизирует установку и прохождение гейтов, документация описывает ожидаемые результаты и советы по отладке.

## Незакрытые задачи и наблюдения
- `claude-workflow-extensions.patch` расширяет агентов/команды; применяйте его вручную и фиксируйте конфликты, если используете дополнительные гейты.
- Собирая новый монорепо, переносите `aidd/` (команды и гейты) и `.claude/` (настройки) под контроль версий — smoke/CI тесты ожидают их наличия.
- Следите за синхронизацией `README.en.md` (метка _Last sync_) после обновлений документации.

## Установка

### Вариант A — `uv tool install` (рекомендуется)

```bash
uv tool install claude-workflow-cli --from git+https://github.com/GrinRus/ai_driven_dev.git
claude-workflow init --target . --commit-mode ticket-prefix --enable-ci
```

- `--target` всегда указывает на workspace; payload разворачивается только в `./aidd`. Запуск CLI/хуков вне `aidd/` приведёт к понятной ошибке «aidd/docs not found».
- первый шаг устанавливает CLI `claude-workflow` в изолированную среду `uv`;
- команда `claude-workflow init` запускает тот же bootstrap, что и `aidd/init-claude-workflow.sh`, копируя шаблоны, гейты и пресеты в текущий проект;
- для EN-локали промптов добавьте `--prompt-locale en` (по умолчанию копируется русская версия `aidd/agents|commands`); каталоги `aidd/prompts/en/**` копируются для редактирования EN-версий;
- CLI разворачивает необходимые Python-модули прямо в `aidd/hooks/_vendor`, поэтому хуки, которые вызывают `python3 -m claude_workflow_cli ...`, работают сразу без отдельного `pip install`;
- для точечной ресинхронизации используйте `claude-workflow sync` (по умолчанию обновляет `.claude/` и `.claude-plugin/`, добавьте `--include claude-presets` или иные каталоги; чтобы подтянуть свежий payload из GitHub Releases, укажите `--release latest` или конкретный тег);
- для быстрого демо воспользуйтесь `claude-workflow preset feature-prd --ticket demo-checkout`.
- если инициализируете повторно, запустите команду в каталоге без старых `.claude/` и `.claude-plugin/` или добавьте `--force`, чтобы перезаписать артефакты.
- для обновления CLI используйте `uv tool upgrade claude-workflow-cli`.

### Вариант B — `pipx`

Если `uv` недоступен, используйте `pipx`:

```bash
pipx install git+https://github.com/GrinRus/ai_driven_dev.git
claude-workflow init --target . --commit-mode ticket-prefix --enable-ci
```

`pipx` добавит CLI в PATH и обеспечит автоматические обновления через `pipx upgrade claude-workflow-cli`.
Повторная инициализация также требует чистого каталога (удалите `.claude/` и `.claude-plugin/` или добавьте `--force` к `claude-workflow init`).

### Вариант C — локально (bash-скрипт)

1. Скачайте репозиторий (git clone или архив) и найдите payload-скрипт `src/claude_workflow_cli/data/payload/aidd/init-claude-workflow.sh`.
2. В вашем проекте создайте каталог `aidd/`.
3. Запустите:

```bash
PAYLOAD_ROOT="/path/to/ai_driven_dev/src/claude_workflow_cli/data/payload/aidd"
mkdir -p aidd
(cd aidd && bash "${PAYLOAD_ROOT}/init-claude-workflow.sh" --commit-mode ticket-prefix --enable-ci)
# опции:
#   --commit-mode ticket-prefix | conventional | mixed
#   --enable-ci   добавить шаблон CI (ручной триггер по умолчанию)
#   --force       перезаписывать существующие файлы
```

После инициализации:

```bash
git add -A && git commit -m "chore: bootstrap Claude Code workflow"
```

## Предпосылки
- `bash`, `git`, `python3`;
- `uv` (https://github.com/astral-sh/uv) или `pipx` для установки CLI (по желанию);
- инструменты сборки/тестов/форматирования вашего стека (по желанию).

Поддерживаются macOS/Linux. На Windows используйте WSL или Git Bash.

## Быстрый старт в Claude Code

Откройте проект в Claude Code и выполните команды:

```
git checkout -b feature/STORE-123
/idea-new STORE-123 checkout-discounts
claude-workflow research --ticket STORE-123 --auto --deep-code --call-graph
/plan-new checkout-discounts
/review-spec checkout-discounts
/tasks-new checkout-discounts
/implement checkout-discounts
/review checkout-discounts
/qa checkout-discounts
```

> Первый аргумент — ticket фичи; при необходимости добавляйте второй параметр как slug-hint (например, `checkout-discounts`), чтобы сохранить человекочитаемый идентификатор в `aidd/docs/.active_feature`.

Результат:
- создаётся цепочка артефактов (PRD, план, tasklist `aidd/docs/tasklist/<ticket>.md`): `/idea-new` сразу сохраняет черновик PRD со статусом `Status: draft`, аналитик фиксирует диалог в `## Диалог analyst`, а ответы даются в формате `Ответ N: …`;
- `claude-workflow research --auto --deep-code` запускается по требованию: сохраняет цели в `reports/research/<ticket>-targets.json`, формирует `aidd/docs/research/<ticket>.md`, добавляет `code_index`/`reuse_candidates`; при нулевых совпадениях CLI помечает отчёт `Status: pending` и добавляет маркер «Контекст пуст, требуется baseline». Пути по умолчанию резолвятся от рабочего корня (parent `aidd/`), CLI выводит `base=workspace:/...` и подсказывает включить `--paths-relative workspace` или передать абсолютные/`../` пути, если граф/матчи пустые.
- при правках на стадии `implement` автоматически запускается `aidd/hooks/format-and-test.sh` (только на Stop/SubagentStop), гейты блокируют изменения в соответствии с `config/gates.json`;
- `git commit` и `/review` работают в связке с чеклистами, помогая довести фичу до статуса READY.
- прогресс каждой итерации фиксируется в `aidd/docs/tasklist/<ticket>.md`: переводите `- [ ] → - [x]`, обновляйте строку `Checkbox updated: …` и запускайте `claude-workflow progress --source <этап> --ticket <ticket>`.

## Чеклист запуска фичи

1. Создайте ветку (`git checkout -b feature/<TICKET>` или вручную) и запустите `/idea-new <ticket> [slug-hint]` — команда автоматически обновит `aidd/docs/.active_ticket`, при необходимости `.active_feature`, **и создаст PRD `aidd/docs/prd/<ticket>.prd.md` со статусом `Status: draft`.** Также фиксируется `aidd/docs/.active_stage=idea` (при смене требований просто перезапустите нужную команду). Ответьте аналитике в формате `Ответ N: …`; если контекста не хватает, инициируйте research (`/researcher` или `claude-workflow research --ticket <ticket> --auto --deep-code --call-graph [--reuse-only]`), затем вернитесь к аналитику и доведите PRD до READY (`claude-workflow analyst-check --ticket <ticket>`).
2. Соберите артефакты аналитики: `/idea-new`, при необходимости `claude-workflow research --ticket <ticket> --auto --deep-code --call-graph`, затем `/plan-new`, `/review-spec`, `/tasks-new` до статуса READY (ticket уже установлен шагом 1). Если проект новый и совпадений нет, оставьте `Status: pending` в `aidd/docs/research/<ticket>.md` с маркером «Контекст пуст, требуется baseline» — гейты разрешат merge только при наличии этого baseline.

   > Call graph (через tree-sitter language pack) по умолчанию фильтруется по `<ticket>|<keywords>` и ограничивается 300 рёбрами (focus) в контексте; полный граф сохраняется отдельно в `reports/research/<ticket>-call-graph-full.json`. Настройка: `--graph-filter/--graph-limit/--graph-langs`.
3. При необходимости включите дополнительные гейты в `config/gates.json` и подготовьте связанные артефакты (миграции, API-спецификации, тесты).
4. Реализуйте фичу малыми шагами через `/implement`, отслеживая сообщения `gate-workflow` и подключённых гейтов. После каждой итерации обновляйте `aidd/docs/tasklist/<ticket>.md`, фиксируйте `Checkbox updated: …` и выполняйте `claude-workflow progress --source implement --ticket <ticket>`.
5. Запросите `/review`, когда чеклисты в `aidd/docs/tasklist/<ticket>.md` закрыты, автотесты зелёные и артефакты синхронизированы, затем повторите `claude-workflow progress --source review --ticket <ticket>`.
6. Перед релизом обязательно выполните `/qa <ticket>` или `claude-workflow qa --ticket <ticket> --report reports/qa/<ticket>.json --gate`, обновите QA-раздел tasklist и подтвердите прогресс `claude-workflow progress --source qa --ticket <ticket>`.
7. После отчётов QA/Review/Research сформируйте handoff-задачи для исполнителя: `claude-workflow tasks-derive --source <qa|review|research> --append --ticket <ticket>` добавит `- [ ]` с ссылками на отчёты в `aidd/docs/tasklist/<ticket>.md`; при необходимости подтвердите прогресс `claude-workflow progress --source handoff --ticket <ticket>`.

Детальный playbook агентов и барьеров описан в `aidd/docs/agents-playbook.md`.

## Слэш-команды

Команды и агенты поставляются как плагин `feature-dev-aidd` в `aidd/.claude-plugin/` (манифест `plugin.json`); файлы живут в `aidd/commands` и `aidd/agents`, а workspace-настройки — в корневом `.claude/`. Фронтматтер команд включает `description`, `argument-hint`, `allowed-tools`, `disable-model-invocation` и позиционные аргументы `$1/$2/$ARGUMENTS`.

| Команда | Назначение | Аргументы (пример) |
| --- | --- | --- |
| `/idea-new` | Собрать вводные и автосоздать PRD (Status: draft → READY) — входы: @aidd/docs/prd.template.md, @aidd/docs/research/<ticket>.md | `STORE-123 checkout-discounts` |
| `/researcher` | Использовать отчёт Researcher и контекст для уточнения области работ | `STORE-123` |
| `/plan-new` | Подготовить план + валидацию — входы: @aidd/docs/prd/<ticket>.prd.md, @aidd/docs/research/<ticket>.md | `checkout-discounts` |
| `/review-spec` | Выполнить review-plan + review-prd — входы: @aidd/docs/plan/<ticket>.md, @aidd/docs/prd/<ticket>.prd.md, @aidd/docs/research/<ticket>.md | `checkout-discounts` |
| `/tasks-new` | Обновить `aidd/docs/tasklist/<ticket>.md` по плану — входы: @aidd/docs/plan/<ticket>.md, @aidd/docs/prd/<ticket>.prd.md, @aidd/docs/research/<ticket>.md | `checkout-discounts` |
| `/implement` | Реализация по плану с автотестами — входы: @aidd/docs/plan/<ticket>.md, @aidd/docs/tasklist/<ticket>.md, @aidd/docs/prd/<ticket>.prd.md | `checkout-discounts` |
| `/review` | Финальное ревью и фиксация статуса — входы: @aidd/docs/prd/<ticket>.prd.md, @aidd/docs/plan/<ticket>.md, @aidd/docs/tasklist/<ticket>.md | `checkout-discounts` |
| `/qa` | Финальная QA-проверка, отчёт `reports/qa/<ticket>.json` — входы: @aidd/docs/prd/<ticket>.prd.md, @aidd/docs/plan/<ticket>.md, @aidd/docs/tasklist/<ticket>.md | `checkout-discounts` |
| `claude-workflow progress` | Проверить наличие новых `- [x]` перед завершением шага | `--source implement --ticket checkout-discounts` |

## Режимы веток и коммитов

Конфигурация хранится в `config/conventions.json` и поддерживает три режима:

- **ticket-prefix** (по умолчанию): `feature/STORE-123` → `STORE-123: краткое описание`;
- **conventional**: `feat/orders` → `feat(orders): краткое описание`;
- **mixed**: `feature/STORE-123/feat/orders` → `STORE-123 feat(orders): краткое описание`.

Измените поле `commit.mode` вручную (`ticket-prefix`/`conventional`/`mixed`) и добавьте git-хук `commit-msg`, чтобы проверять сообщения — пример настроек в `aidd/docs/customization.md`.

## Выборочные тесты

Скрипт `aidd/hooks/format-and-test.sh`:
1. Читает `automation.tests` в `.claude/settings.json` (runner, `defaultTasks`, `fallbackTasks`, `moduleMatrix`).
2. Анализирует `git diff` + незакоммиченные файлы, оставляя только релевантные пути.
3. Сопоставляет пути с `moduleMatrix` и формирует команды тест‑раннера; если матчей нет — использует `defaultTasks`/`fallbackTasks`.
4. Работает в «мягком» режиме — падение тестов не блокирует коммит (можно ужесточить через `STRICT_TESTS`).
5. Запускается автоматически на Stop/SubagentStop только при стадии `implement`; чтобы временно отключить автозапуск, выставьте `SKIP_AUTO_TESTS=1`.

Подробности и советы по тройблшутингу собраны в `aidd/workflow.md` и `aidd/docs/customization.md`.

## Дополнительно
- Пошаговый пример использования и снимки до/после: `examples/apply-demo.sh` и раздел «Обзор этапов» в `aidd/workflow.md`.
- Подробный обзор цикла и гейтов: `aidd/workflow.md`.
- Playbook агентов и барьеров: `aidd/docs/agents-playbook.md`.
- Руководство по настройке `.claude/settings.json`, `config/conventions.json`, хуков и вспомогательных скриптов: `aidd/docs/customization.md`.
- Англоязычная версия README с правилами синхронизации: `README.en.md`.
- Демо-сценарии и скрипт применения: `examples/`, `examples/apply-demo.sh`.
- Быстрая справка по слэш-командам: `aidd/commands/`.

## Миграция на agent-first
1. **Обновите репозиторий и payload.** Выполните `git pull`, затем `scripts/sync-payload.sh --direction=from-root && python3 tools/check_payload_sync.py`, чтобы новые шаблоны PRD/tasklist/research и команда `/idea-new` попали в проект и CLI payload.
2. **Обновите `aidd/agents|commands` и prompts.** Скопируйте свежие версии (RU/EN) в свой проект или переустановите workflow; убедитесь, что `templates/prompt-agent.md`/`prompt-command.md` совпадают, чтобы новые агенты сразу работали в стиле agent-first.
3. **Освежите активные тикеты.** Для каждой фичи выполните `claude-workflow research --ticket <ticket> --auto` (пересоберёт `reports/research/*.json` и шаблон research), затем `claude-workflow analyst-check --ticket <ticket>` — это подтвердит, что PRD и research соответствуют новым требованиям. При необходимости вручную перенесите разделы «Автоматизация»/«Команды» из обновлённых шаблонов в уже существующие артефакты.
4. **Проверьте тесты и гейты.** Запустите `scripts/ci-lint.sh` и smoke-сценарии (`scripts/smoke-workflow.sh`) — они проверят, что tasklist содержит новые поля `Reports/Commands`, а промпты не содержат устаревших `Answer N` инструкций.
5. **Документируйте миграцию.** Добавьте заметку в `aidd/docs/release-notes.md`/`CHANGELOG.md` вашего проекта, чтобы команда знала о новых правилах вопросов, логах команд и репозиторных источниках.

## Релизы CLI
- Версия берётся из `pyproject.toml`; пуш в `main` автоматически создаёт тег `v<версия>` (`.github/workflows/autotag.yml`), если такого ещё нет.
- Тег `v*` запускает workflow `release.yml`: собираются `sdist`/`wheel` (`python -m build`), артефакты прикрепляются к GitHub Release и сохраняются как artefact.
- Пользователи устанавливают CLI напрямую из репозитория: `uv tool install claude-workflow-cli --from git+https://github.com/GrinRus/ai_driven_dev.git` или `pipx install git+https://github.com/GrinRus/ai_driven_dev.git[@tag]`.
- Перед релизом обновляйте `CHANGELOG.md` и README, проверяйте `scripts/ci-lint.sh` и `claude-workflow smoke`. После релиза убедитесь, что релиз появился в разделе GitHub Releases и что указанные инструкции по установке актуальны.

## Вклад и лицензия
- Перед отправкой изменений ознакомьтесь с `CONTRIBUTING.md`.
- Лицензия проекта — MIT (`LICENSE`).
- Проект не аффилирован с поставщиками IDE/инструментов; используйте на свой риск.
