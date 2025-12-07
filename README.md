# Claude Code Workflow — Java/Kotlin Monorepo Template

> Готовый GitHub-шаблон и инсталлятор, который подключает Claude Code к вашему Java/Kotlin монорепозиторию, добавляет слэш-команды, безопасные хуки и выборочный запуск Gradle-тестов.

## TL;DR
- `/init-claude-workflow.sh` разворачивает цикл `/idea-new → claude-workflow research --deep-code → /plan-new → /review-prd → /tasks-new → /implement → /review` с защитными хуками и автоматическим запуском тестов.
- Автоформат и выборочные Gradle-тесты запускаются после каждой правки (можно отключить `SKIP_AUTO_TESTS=1`), артефакты защищены хуками `gate-*`.
- Настраиваемые режимы веток/коммитов через `config/conventions.json` и готовые шаблоны документации.
- Опциональные интеграции с GitHub Actions, Issue/PR шаблонами и политиками доступа Claude Code.

## Оглавление
- [Что входит в шаблон](#что-входит-в-шаблон)
- [Архитектура workflow](#архитектура-workflow)
- [Agent-first принципы](#agent-first-принципы)
- [Структура репозитория](#структура-репозитория)
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
- [Выборочные тесты Gradle](#выборочные-тесты-gradle)
- [Дополнительно](#дополнительно)
- [Миграция на agent-first](#миграция-на-agent-first)
- [Вклад и лицензия](#вклад-и-лицензия)

## Что входит в шаблон
- Слэш-команды Claude Code и саб-агенты для подготовки PRD/ADR/Tasklist, генерации документации и валидации коммитов.
- Многошаговый workflow (идея → план → PRD review → задачи → реализация → ревью → QA) с саб-агентами `analyst/planner/prd-reviewer/validator/implementer/reviewer/qa`; дополнительные проверки включаются через `config/gates.json`.
- Git-хуки для автоформатирования, запуска выборочных тестов и workflow-гейтов.
- Конфигурация коммитов (`ticket-prefix`, `conventional`, `mixed`) и вспомогательные скрипты CLI.
- Базовый набор документации, issue/PR шаблонов и CI workflow (включается флагом `--enable-ci`).
- Локальная, прозрачная установка без зависимости от Spec Kit или BMAD.

## Архитектура workflow
1. `init-claude-workflow.sh` разворачивает структуру `.claude/`, конфиги и шаблоны.
2. Slash-команды Claude Code запускают многошаговый процесс (см. `workflow.md`): от идеи и плана до реализации и ревью, подключая специализированных саб-агентов.
3. Пресет `strict` в `.claude/settings.json` включает `gate-workflow` и автозапуск `.claude/hooks/format-and-test.sh`; дополнительные гейты (`gate-tests`, `gate-qa`) включаются флагами в `config/gates.json`.
4. Git-хук `format-and-test.sh` выполняет форматирование и выборочные Gradle-тесты; полный прогон инициируется при изменении общих артефактов.
5. Политики доступа и режимы веток/коммитов управляются через `.claude/settings.json` и `config/conventions.json`.

Детали настройки и расширения описаны в `workflow.md` и `docs/customization.md`.

## Agent-first принципы
- **Сначала slug-hint и артефакты, затем вопросы.** Аналитик начинает со `docs/.active_feature` (пользовательский slug-hint), затем читает `docs/research/<ticket>.md`, `reports/research/*.json` (включая `code_index`/`reuse_candidates`), существующие планы/ADR и только потом формирует Q&A для пробелов. Исследователь фиксирует каждую команду (`claude-workflow research --auto --deep-code`, `rg "<ticket>" src/**`, `find`, `python`) и строит call/import graph Claude Code'ом, а implementer обновляет tasklist и перечисляет запущенные `./gradlew`/`claude-workflow progress` перед тем как обращаться к пользователю.
- **Команды и логи — часть ответа.** Все промпты и шаблоны требуют указывать разрешённые CLI (Gradle, `rg`, `claude-workflow`) и прикладывать вывод/пути, чтобы downstream-агенты могли воспроизвести шаги. Tasklist и research-шаблон теперь содержат разделы «Commands/Reports».
- **Автогенерация артефактов.** `/idea-new` автоматически создаёт PRD, обновляет отчёты Researcher и инструктирует аналитика собирать данные из репозитория. Пресеты `templates/prompt-agent.md` и `templates/prompt-command.md` подсказывают, как описывать входы, гейты, команды и fail-fast блоки в стиле agent-first.

## Структура репозитория
| Каталог/файл | Назначение | Ключевые детали |
| --- | --- | --- |
| `.claude/settings.json` | Политики доступа и автоматизации | Пресеты `start`/`strict`, pre/post-хуки, auto-форматирование/тесты, защита prod-путей |
| `.claude/commands/` | Инструкция для слэш-команд | Маршруты `/idea-new`, `/researcher`, `/plan-new`, `/review-prd`, `/tasks-new`, `/implement`, `/review` с `allowed-tools` и встроенными shell-шагами |
| `.claude/agents/` | Playbook саб-агентов | Роли `analyst`, `planner`, `prd-reviewer`, `validator`, `implementer`, `reviewer`, `qa` |
| `prompts/en/` | EN-версии промптов | `prompts/en/agents/*.md`, `prompts/en/commands/*.md`, синхронизированы с `.claude/**` (см. `docs/prompt-versioning.md`) |
| `.claude/hooks/` | Защитные и утилитарные хуки | `gate-workflow.sh`, `gate-prd-review.sh`, `gate-tests.sh`, `gate-qa.sh`, `lint-deps.sh`, `format-and-test.sh` |
| `.claude/gradle/` *(создаётся при установке)* | Gradle-хелперы | `init-print-projects.gradle` объявляет задачу `ccPrintProjectDirs` для selective runner |
| `config/gates.json` | Параметры гейтов | Управляет `prd_review`, `tests_required`, `deps_allowlist`, `qa`, `feature_ticket_source`, `feature_slug_hint_source` |
| `config/conventions.json` | Режимы веток и коммитов | Расписаны шаблоны `ticket-prefix`, `conventional`, `mixed`, правила ветвления и ревью |
| `config/allowed-deps.txt` | Allowlist зависимостей | Формат `group:artifact`; предупреждения выводит `lint-deps.sh` |
| `docs/` | Руководства и шаблоны | `customization.md`, `agents-playbook.md`, `qa-playbook.md`, `feature-cookbook.md`, `release-notes.md`, шаблоны PRD/ADR/tasklist, рабочие артефакты фич |
| `examples/` | Демо-материалы | Сценарий `apply-demo.sh`, заготовка Gradle-монорепо `gradle-demo/` |
| `scripts/` | CLI и вспомогательные сценарии | `ci-lint.sh` (линтеры + тесты), `smoke-workflow.sh` (E2E smoke сценарий gate-workflow), `prd-review-agent.py` (эвристика ревью PRD), `qa-agent.py` (эвристический QA-агент), `bootstrap-local.sh` (локальное dogfooding payload) |
| `templates/` | Шаблоны вендорных артефактов | Git-хуки (`commit-msg`, `pre-push`, `prepare-commit-msg`) и расширенный шаблон `docs/tasklist/<ticket>.md` |
| `tests/` | Python-юнит-тесты | Проверяют init-скрипт, хуки, selective tests и настройки доступа |
| `.github/workflows/ci.yml` | CI pipeline | Запускает `scripts/ci-lint.sh`, ставит `shellcheck`, `markdownlint`, `yamllint` |
| `init-claude-workflow.sh` | Bootstrap-скрипт | Флаги `--commit-mode`, `--enable-ci`, `--force`, `--dry-run`, проверка зависимостей и генерация структуры |
| `workflow.md` | Процессная документация | Детальный сценарий idea → research → plan → PRD review → tasks → implement → review |
| `claude-workflow-extensions.patch` | Пакет расширений | Diff с дополнительными агентами, гейтами и командами для продвинутых установок |
| `README.en.md` | Англоязычный README | Синхронизируется с этой версией, содержит пометку _Last sync_ |
| `CONTRIBUTING.md` | Правила вкладов | Описывает процесс PR/issue, требования к коммитам и линтингу |
| `LICENSE` | Лицензия | MIT с ограничениями ответственности |

> `init-claude-workflow.sh` разворачивает `.claude/hooks/*`, документацию и вспомогательный Gradle-скрипт `.claude/gradle/init-print-projects.gradle`. Ветки и сообщения коммитов настраиваются стандартными git-командами по правилам `config/conventions.json`.

## Детальный анализ компонентов

### Скрипты установки и утилиты
- `init-claude-workflow.sh` — модульный bootstrap со строгими проверками (`bash/git/python3`, Gradle/ktlint), режимами `--commit-mode/--enable-ci/--force/--dry-run` и потоковой синхронизацией артефактов из `src/claude_workflow_cli/data/payload/` (без heredoc-вставок), включая обновление `config/conventions.json`.
- `scripts/ci-lint.sh` — единая точка для `shellcheck`, `markdownlint`, `yamllint` и `python -m unittest`, интегрированная с CI и корректно пропускающая отсутствующие линтеры с предупреждением.
- `scripts/smoke-workflow.sh` — E2E smoke-сценарий: поднимает временный проект, запускает bootstrap, воспроизводит ticket-first цикл (`ticket → PRD → план → tasklist`) и проверяет, что `gate-workflow.sh`/`tasklist_progress` блокируют правки без новых `- [x]`.
- `scripts/bootstrap-local.sh` — копирует `src/claude_workflow_cli/data/payload/` в `.dev/.claude-example/` (или произвольный `--target`), чтобы быстро проверить изменения payload без публикации новой версии CLI.
- `claude-workflow sync` / `claude-workflow upgrade` — поддерживают режим `--release <tag|owner/repo@tag|latest>` для скачивания payload из GitHub Releases (кешируется в `~/.cache/claude-workflow`, переопределяется `--cache-dir` или `CLAUDE_WORKFLOW_CACHE`). CLI сверяет контрольные суммы из `manifest.json`, перед синхронизацией выводит diff и при недоступности сети откатывается к встроенному payload.
- `examples/apply-demo.sh` — демонстрирует применение шаблона к Gradle-монорепо, печатает дерево каталогов до/после и, при наличии wrapper, запускает `gradlew test`.

### Git-хуки и автоматизация
- `.claude/hooks/format-and-test.sh` — Python-хук, который читает `.claude/settings.json`, учитывает `SKIP_FORMAT`, `FORMAT_ONLY`, `TEST_SCOPE`, `STRICT_TESTS`, `SKIP_AUTO_TESTS`, анализирует `git diff`, активный ticket (и slug-хинт) из `docs/.active_ticket`/`.active_feature`, умеет переключать selective/full run и подбирает задачи через `moduleMatrix`, `defaultTasks`, `fallbackTasks`.
- `.claude/hooks/gate-workflow.sh` — блокирует правки под `src/**`, если для активного ticket нет PRD, плана или новых `- [x]` в `docs/tasklist/<ticket>.md` (гейт `tasklist_progress`), игнорирует изменения в документации/шаблонах.
- `.claude/hooks/gate-tests.sh` — опциональная проверка из `config/gates.json`: контролирует наличие сопутствующих тестов (`disabled|soft|hard`) и выводит подсказки по разблокировке.
- `.claude/hooks/gate-qa.sh` — вызывает `scripts/qa-agent.py`, формирует `reports/qa/<ticket>.json`, маркирует `blocker/critical` как блокирующие; см. `docs/qa-playbook.md`.
- `.claude/hooks/lint-deps.sh` — отслеживает изменения зависимостей, сверяет их с allowlist `config/allowed-deps.txt` и сигнализирует при расхождениях.
- `.claude/gradle/init-print-projects.gradle` — вспомогательный скрипт, регистрирует задачу `ccPrintProjectDirs` для построения кеша модулей selective runner.

### Саб-агенты Claude Code
- `.claude/agents/analyst.md` — формализует идею в PRD со статусом READY/BLOCKED, задаёт уточняющие вопросы, фиксирует риски/допущения и обновляет `docs/prd/<ticket>.prd.md`.
- `.claude/agents/planner.md` — строит пошаговый план (`docs/plan/<ticket>.md`) с DoD и зависимостями; `.claude/agents/validator.md` проверяет план и записывает вопросы для продуктов/архитекторов.
- `.claude/agents/implementer.md` — ведёт реализацию малыми итерациями, отслеживает гейты, обновляет чеклист (`Checkbox updated: …`, передаёт новые `- [x]`) и вызывает `claude-workflow progress --source implement`.
- `.claude/agents/reviewer.md` — оформляет код-ревью, проверяет чеклисты, ставит статусы READY/BLOCKED, фиксирует follow-up в `docs/tasklist/<ticket>.md` и запускает `claude-workflow progress --source review`.
- `.claude/agents/qa.md` — финальная QA-проверка; готовит отчёт с severity, обновляет `docs/tasklist/<ticket>.md`, запускает `claude-workflow progress --source qa` и взаимодействует с `gate-qa.sh`.

### Слэш-команды и пайплайн
- Ветки создайте `git checkout -b feature/<TICKET>` или по другим паттернам из `config/conventions.json`.
- `.claude/commands/idea-new.md` — фиксирует ticket (и при необходимости slug-хинт) в `docs/.active_ticket`/`.active_feature`, сразу запускает `claude-workflow research --ticket <ticket> --auto`, вызывает `analyst`, **создаёт черновик `docs/prd/<ticket>.prd.md` (Status: draft)** и открытые вопросы.
- `.claude/commands/researcher.md` — собирает контекст (CLI `claude-workflow research`) и оформляет отчёт `docs/research/<ticket>.md`.
- `.claude/commands/plan-new.md` — подключает `planner` и `validator`, обновляет план и протокол проверки.
- `.claude/commands/tasks-new.md` — синхронизирует `docs/tasklist/<ticket>.md` с планом, распределяя задачи по этапам и заполняя slug-хинт/артефакты.
- `.claude/commands/implement.md` — фиксирует шаги реализации, напоминает про гейты и автоматические тесты.
- `.claude/commands/review.md` — оформляет ревью, обновляет чеклисты и статус READY/BLOCKED.
- Сообщения коммитов формируйте вручную (`git commit`), сверяясь со схемами в `config/conventions.json`.

### Конфигурация и политики
- `.claude/settings.json` — пресеты `start/strict`, списки `allow/ask/deny` и параметры `automation` (формат/тесты).
- `config/conventions.json` — commit/branch режимы (`ticket-prefix`, `conventional`, `mixed`), шаблоны сообщений, примеры, заметки для ревью и CLI.
- `config/gates.json` — флаги `tests_required`, `deps_allowlist`, `qa`, `feature_ticket_source`, `feature_slug_hint_source`; управляет поведением гейтов и `lint-deps.sh`.
- `config/allowed-deps.txt` — allowlist `group:artifact`, поддерживает комментарии, используется `lint-deps.sh`.

### Документация и шаблоны
- `workflow.md`, `docs/customization.md`, `docs/agents-playbook.md` — описывают процесс idea→research→review, walkthrough установки, настройку `.claude/settings.json` и роли саб-агентов.
- `docs/prd.template.md`, `docs/adr.template.md`, `docs/tasklist.template.md`, `templates/tasklist.md` — шаблоны с подсказками, чеклистами, секциями истории изменений и примерами заполнения.
- `templates/git-hooks/*.sample`, `templates/git-hooks/README.md` — готовые `commit-msg`, `prepare-commit-msg`, `pre-push` с инструкциями, переменными окружения и советами по развёртыванию.
- `docs/release-notes.md` — регламент релизов и checklist обновлений (используется для планирования roadmap и changelog).

### Тесты и контроль качества
- `tests/helpers.py` — утилиты: генерация файлов, git init/config, создание `config/gates.json`, запуск хуков.
- `tests/test_init_claude_workflow.py` — проверка bootstrap-скрипта, флагов `--dry-run`, `--force`, наличия ключевых артефактов.
- `tests/test_gate_*.py` — сценарии для гейтов workflow, API, миграций БД, обязательных тестов; учитывают tracked/untracked миграции и пропуски нецелевых файлов.
- `tests/test_format_and_test.py` — покрытие selective runner: `moduleMatrix`, общие файлы, переменные `TEST_SCOPE`, `SKIP_AUTO_TESTS`.
- `tests/test_settings_policy.py` — защита `permissions`/`hooks` в `.claude/settings.json`, гарантирует, что критичные команды остаются в `ask/deny`.

### Демо и расширения
- `examples/gradle-demo/` — двухсервисный Gradle-монорепо (модули `service-checkout`, `service-payments`) на Kotlin 1.9.22 с общим `jvmToolchain(17)` и настройками `JUnit 5`.
- `claude-workflow-extensions.patch` — patch-файл с расширениями агентов, команд и гейтов, готовый к применению на чистый репозиторий.

## Архитектура и взаимосвязи
- Инициализация (`init-claude-workflow.sh`) генерирует настройки `.claude/settings.json`, гейты и слэш-команды, которые затем задействуются hook-пайплайном.
- Пресет `strict` в `.claude/settings.json` подключает pre/post-хуки и автоматически запускает `.claude/hooks/format-and-test.sh` после успешной записи.
- Гейты (`gate-*`) читают `config/gates.json` и артефакты в `docs/**`, обеспечивая прохождение цепочки `/idea-new → claude-workflow research → /plan-new → /review-prd → /tasks-new`; включайте дополнительные проверки (`researcher`, `prd_review`, `tests_required`) по мере необходимости.
- `.claude/hooks/format-and-test.sh` опирается на Gradle-скрипт `init-print-projects.gradle`, сохранённый ticket (и slug-хинт) и `moduleMatrix`, чтобы решать, запускать ли selective или полный набор задач.
- Тестовый набор на Python использует `tests/helpers.py` для эмуляции git/файловой системы, покрывая dry-run, tracked/untracked изменения и поведение хуков.

## Ключевые скрипты и хуки
- **`init-claude-workflow.sh`** — валидирует `bash/git/python3`, ищет Gradle/kotlin-линтеры, генерирует каталоги `.claude/ config/ docs/ templates/`, перезаписывает артефакты по `--force`, выводит dry-run и настраивает режим коммитов.
- **`.claude/hooks/format-and-test.sh`** — анализирует `git diff`, собирает задачи из `automation.tests` (`changedOnly`, `moduleMatrix`), уважает `SKIP_FORMAT`, `FORMAT_ONLY`, `TEST_SCOPE`, `STRICT_TESTS`, `SKIP_AUTO_TESTS` и умеет подстраивать полный прогон при изменении общих файлов.
- **`gate-prd-review.sh`** — вызывает `scripts/prd_review_gate.py`, который требует наличие `docs/prd/<ticket>.prd.md`, секции `## PRD Review` со статусом из `approved_statuses`, закрытые action items и JSON-отчёт (`reports/prd/<ticket>.json` по умолчанию); блокирующие статусы, `- [ ]` и findings с severity из `blocking_severities` завершают проверку ошибкой, а флаги `skip_branches`, `allow_missing_section`, `allow_missing_report` и шаблон `report_path` задаются в `config/gates.json`.
- **`gate-workflow.sh`** — блокирует изменения в `src/**`, пока не создана цепочка PRD/план/tasklist для активной фичи (`docs/.active_ticket`) и не появилось новых `- [x]` в `docs/tasklist/<ticket>.md`.
- **`gate-tests.sh`** — опциональный гейт: при включении проверяет наличие тестов `src/test/**` (режимы задаёт `config/gates.json`).
- **`lint-deps.sh`** — напоминает про allowlist зависимостей из `config/allowed-deps.txt` и анализирует изменения Gradle-конфигураций.
- **`scripts/ci-lint.sh`** — единая точка для `shellcheck`, `markdownlint`, `yamllint` и `python -m unittest`, используется локально и в GitHub Actions.
- **`scripts/smoke-workflow.sh`** — поднимает временной проект, гоняет init-скрипт и проверяет прохождение `gate-workflow` по шагам `/idea-new → /plan-new → /review-prd → /tasks-new`.
- **`examples/apply-demo.sh`** — пошагово применяет шаблон к директории с Gradle-модулями, демонстрируя интеграцию с `gradlew`.
- **`scripts/prompt-release.sh`** — автоматизирует bump версий промптов (`scripts/prompt-version`), линтер, pytest-наборы и проверку payload/gate перед подготовкой релиза.
- **`scripts/scaffold_prompt.py`** — разворачивает шаблоны `templates/prompt-agent.md` / `templates/prompt-command.md`, подставляет фронт-маттер и создаёт новые промпты (`--type agent|command`, `--target ...`, `--force`).

## Тестовый контур
- `tests/helpers.py` — вспомогательные функции (создание файлов, git init/config, запуск хуков) для изоляции сценариев.
- `tests/test_init_claude_workflow.py` — проверяет чистую установку, `--dry-run`, `--force`, наличие ключевых артефактов и поведение bootstrap-скрипта.
- `tests/test_gate_*.py` — проверяют workflow/API/DB/tests гейты: учитывают ticket/slug-хинт, tracked/untracked миграции, режимы `soft/hard/disabled` и нецелевые файлы.
- `tests/test_format_and_test.py` — моделирует запуск Python-хука, проверяет `moduleMatrix`, реакцию на общие файлы, переменные `SKIP_AUTO_TESTS`, `TEST_SCOPE`.
- `tests/test_settings_policy.py` — валидирует `.claude/settings.json`, гарантируя, что критичные команды (`git add/commit/push`, `curl`, запись в прод-пути) находятся в `ask/deny`.
- `scripts/ci-lint.sh` и `.github/workflows/ci.yml` — единый entrypoint линтеров/тестов для локального запуска и GitHub Actions.
- `scripts/smoke-workflow.sh` — E2E smoke, подтверждает, что `gate-workflow` блокирует исходники до появления PRD/плана/tasklist (`docs/tasklist/<ticket>.md`).

## Диагностика и отладка
- **Линтеры и тесты:** запускайте `scripts/ci-lint.sh` для полного набора (`shellcheck`, `markdownlint`, `yamllint`, `python -m unittest`) или адресно `python3 -m unittest tests/test_gate_workflow.py`.
- **Переменные окружения:** `SKIP_AUTO_TESTS`, `SKIP_FORMAT`, `FORMAT_ONLY`, `TEST_SCOPE`, `TEST_CHANGED_ONLY`, `STRICT_TESTS` управляют `.claude/hooks/format-and-test.sh`.
- **Диагностика гейтов:** передайте payload через stdin: `echo '{"tool_input":{"file_path":"src/main/kotlin/App.kt"}}' | CLAUDE_PROJECT_DIR=$PWD .claude/hooks/gate-workflow.sh`.
- **Selective runner:** выполните `./gradlew -I .claude/gradle/init-print-projects.gradle ccPrintProjectDirs` — задача выведет пары `:module:/abs/path`; перенаправьте вывод в `.claude/cache/project-dirs.txt` или используйте результат для обновления `automation.tests.moduleMatrix`.
- **Smoke-сценарий:** `scripts/smoke-workflow.sh` поднимет временной проект и проверит последовательность `/idea-new → /plan-new → /review-prd → /tasks-new`.
- **CI-проверки:** GitHub Actions (`.github/workflows/ci.yml`) ожидает установленные `shellcheck`, `yamllint`, `markdownlint`; убедитесь, что локальная среда воспроизводит их версии при отладке.

## Политики доступа и гейты
- `.claude/settings.json` содержит пресеты `start` и `strict`: первый позволяет базовые операции, второй включает pre- и post-хуки (`gate-*`, `format-and-test`, `lint-deps`) и требует явного подтверждения `git add/commit/push`.
- Раздел `automation` управляет форматированием и тестами; настройте `format`/`tests` под ваш Gradle-пайплайн.
- `config/gates.json` централизует флаги `prd_review`, `tests_required`, `deps_allowlist`, а также пути к активному ticket (`feature_ticket_source`) и slug-хинту (`feature_slug_hint_source`); для `prd_review` доступны параметры `approved_statuses`, `blocking_statuses`, `blocking_severities`, `allow_missing_section`, `allow_missing_report`, `report_path`, `skip_branches` и `branches`.
- Комбинация хуков `gate-*` в `.claude/hooks/` реализует согласованную политику: блокировка кода без артефактов, требование миграций и тестов, контроль API-контрактов.

## Документация и шаблоны
- `workflow.md`, `docs/agents-playbook.md` — описывают целевой цикл idea→review, роли саб-агентов и взаимодействие с гейтами.
- `workflow.md`, `docs/customization.md` — walkthrough применения bootstrap к Gradle-монорепо и подробности настройки `.claude/settings.json`, гейтов, шаблонов команд.
- `docs/release-notes.md` — регламент релизов и планирование roadmap.
- `docs/prompt-playbook.md` — единые правила оформления промптов агентов/команд (обязательные секции, `Checkbox updated`, Fail-fast, ссылки на артефакты и матрица ролей).
- `docs/prompt-versioning.md` — политика двуязычных промптов, правила `prompt_version`, `Lang-Parity: skip`, скрипты `prompt-version` и `prompt_diff`.
- `templates/prompt-agent.md`, `templates/prompt-command.md`, `claude-presets/advanced/prompt-governance.yaml` — шаблоны и пресет для генерации новых промптов; используйте вместе со скриптом `scripts/scaffold_prompt.py`.
- Шаблоны PRD/ADR/tasklist (`docs/*.template.md`, `templates/tasklist.md`) и git-хуки (`templates/git-hooks/*.sample`) — расширенные заготовки с подсказками, чеклистами и переменными окружения.
- `README.en.md` — синхронизированный перевод; при правках обновляйте обе версии и поле Last sync.

## Примеры и демо
- `examples/gradle-demo/` — двухсервисный Gradle-монорепо (Kotlin 1.9.22, `jvmToolchain(17)`, JUnit 5), демонстрирующий структуру модулей и пригодный для selective тестов.
- `examples/apply-demo.sh` — пошаговый сценарий применения bootstrap к демо-проекту, полезен для воркшопов и презентаций.
- `scripts/smoke-workflow.sh` + `workflow.md` — живой пример: скрипт автоматизирует установку и прохождение гейтов, документация описывает ожидаемые результаты и советы по отладке.

## Незакрытые задачи и наблюдения
- `claude-workflow-extensions.patch` расширяет агентов/команды; применяйте его вручную и фиксируйте конфликты, если используете дополнительные гейты.
- Собирая новый монорепо, переносите `.claude/` (команды, гейты, Gradle-хелпер) под контроль версий — smoke/CI тесты ожидают их наличия.
- Следите за синхронизацией `README.en.md` (метка _Last sync_) после обновлений документации.

## Установка

### Вариант A — `uv tool install` (рекомендуется)

```bash
uv tool install claude-workflow-cli --from git+https://github.com/GrinRus/ai_driven_dev.git
claude-workflow init --target . --commit-mode ticket-prefix --enable-ci
```

- первый шаг устанавливает CLI `claude-workflow` в изолированную среду `uv`;
- команда `claude-workflow init` запускает тот же bootstrap, что и `init-claude-workflow.sh`, копируя шаблоны, гейты и пресеты в текущий проект;
- для EN-локали промптов добавьте `--prompt-locale en` (по умолчанию копируется русская версия `.claude/agents|commands`); каталоги `prompts/en/**` копируются для редактирования EN-версий;
- CLI разворачивает необходимые Python-модули прямо в `.claude/hooks/_vendor`, поэтому хуки, которые вызывают `python3 -m claude_workflow_cli ...`, работают сразу без отдельного `pip install`;
- для точечной ресинхронизации используйте `claude-workflow sync` (по умолчанию обновляет `.claude/`, добавьте `--include claude-presets` или иные каталоги; чтобы подтянуть свежий payload из GitHub Releases, укажите `--release latest` или конкретный тег);
- для быстрого демо воспользуйтесь `claude-workflow preset feature-prd --ticket demo-checkout`.
- если инициализируете повторно, запустите команду в каталоге без старого `.claude/` или добавьте `--force`, чтобы перезаписать артефакты.
- для обновления CLI используйте `uv tool upgrade claude-workflow-cli`.

### Вариант B — `pipx`

Если `uv` недоступен, используйте `pipx`:

```bash
pipx install git+https://github.com/GrinRus/ai_driven_dev.git
claude-workflow init --target . --commit-mode ticket-prefix --enable-ci
```

`pipx` добавит CLI в PATH и обеспечит автоматические обновления через `pipx upgrade claude-workflow-cli`.
Повторная инициализация также требует чистого каталога (удалите `.claude/` или добавьте `--force` к `claude-workflow init`).

### Вариант C — локально (bash-скрипт)

1. Скачайте каталог репозитория (git clone или архив) и перейдите в него.
2. Скопируйте `init-claude-workflow.sh` рядом с вашим проектом.
3. Запустите:

```bash
bash init-claude-workflow.sh --commit-mode ticket-prefix --enable-ci
# опции:
#   --commit-mode ticket-prefix | conventional | mixed
#   --enable-ci   добавить шаблон CI (ручной триггер по умолчанию)
#   --force       перезаписывать существующие файлы
```

Альтернатива для публичных репозиториев — загрузить скрипт напрямую:

```bash
curl -fsSL https://raw.githubusercontent.com/GrinRus/ai_driven_dev/main/init-claude-workflow.sh \
  | bash -s -- --commit-mode ticket-prefix --enable-ci
```

После инициализации:

```bash
git add -A && git commit -m "chore: bootstrap Claude Code workflow"
```

## Предпосылки
- `bash`, `git`, `python3`;
- `uv` (https://github.com/astral-sh/uv) или `pipx` для установки CLI (по желанию);
- Gradle wrapper (`./gradlew`) или установленный Gradle;
- (опционально) `ktlint` и/или Spotless для автоформатирования.

Поддерживаются macOS/Linux. На Windows используйте WSL или Git Bash.

## Быстрый старт в Claude Code

Откройте проект в Claude Code и выполните команды:

```
git checkout -b feature/STORE-123
/idea-new STORE-123 checkout-discounts
claude-workflow research --ticket STORE-123 --auto --deep-code --call-graph
/plan-new checkout-discounts
/review-prd checkout-discounts
/tasks-new checkout-discounts
/implement checkout-discounts
/review checkout-discounts
```

> Первый аргумент — ticket фичи; при необходимости добавляйте второй параметр как slug-hint (например, `checkout-discounts`), чтобы сохранить человекочитаемый идентификатор в `docs/.active_feature`.

Результат:
- создаётся цепочка артефактов (PRD, план, tasklist `docs/tasklist/<ticket>.md`): `/idea-new` сразу сохраняет черновик PRD со статусом `Status: draft`, аналитик фиксирует диалог в `## Диалог analyst`, а ответы даются в формате `Ответ N: …`;
- `claude-workflow research --auto --deep-code` сохраняет цели в `reports/research/<ticket>-targets.json`, формирует `docs/research/<ticket>.md`, добавляет `code_index`/`reuse_candidates`; при нулевых совпадениях CLI помечает отчёт `Status: pending` и добавляет маркер «Контекст пуст, требуется baseline».
- при правках автоматически запускается `.claude/hooks/format-and-test.sh`, гейты блокируют изменения в соответствии с `config/gates.json`;
- `git commit` и `/review` работают в связке с чеклистами, помогая довести фичу до статуса READY.
- прогресс каждой итерации фиксируется в `docs/tasklist/<ticket>.md`: переводите `- [ ] → - [x]`, обновляйте строку `Checkbox updated: …` и запускайте `claude-workflow progress --source <этап> --ticket <ticket>`.

## Чеклист запуска фичи

1. Создайте ветку (`git checkout -b feature/<TICKET>` или вручную) и запустите `/idea-new <ticket> [slug-hint]` — команда автоматически обновит `docs/.active_ticket`, при необходимости `.active_feature`, **и создаст PRD `docs/prd/<ticket>.prd.md` со статусом `Status: draft`.** Сразу после этого выполните `claude-workflow research --ticket <ticket> --auto --deep-code --call-graph [--reuse-only]`, чтобы зафиксировать цели/контекст (добавьте `--note` для свободного ввода); отвечайте на вопросы аналитика в формате `Ответ N: …`, пока не обновите `Status: READY` и не пройдёте `claude-workflow analyst-check --ticket <ticket>`.
2. Соберите артефакты аналитики: `/idea-new`, `claude-workflow research --ticket <ticket> --auto --deep-code --call-graph`, `/plan-new`, `/review-prd`, `/tasks-new` до статуса READY/PASS (ticket уже установлен шагом 1). Если проект новый и совпадений нет, оставьте `Status: pending` в `docs/research/<ticket>.md` с маркером «Контекст пуст, требуется baseline» — гейты разрешат merge только при наличии этого baseline.

   > Call graph (Java/Kotlin через tree-sitter) по умолчанию фильтруется по `<ticket>|<keywords>` и ограничивается 300 рёбрами (focus) в контексте; полный граф сохраняется отдельно в `reports/research/<ticket>-call-graph-full.json`. Настройка: `--graph-filter/--graph-limit/--graph-langs`.
3. При необходимости включите дополнительные гейты в `config/gates.json` и подготовьте связанные артефакты (миграции, API-спецификации, тесты).
4. Реализуйте фичу малыми шагами через `/implement`, отслеживая сообщения `gate-workflow` и подключённых гейтов. После каждой итерации обновляйте `docs/tasklist/<ticket>.md`, фиксируйте `Checkbox updated: …` и выполняйте `claude-workflow progress --source implement --ticket <ticket>`.
5. Запросите `/review`, когда чеклисты в `docs/tasklist/<ticket>.md` закрыты, автотесты зелёные и артефакты синхронизированы, затем повторите `claude-workflow progress --source review --ticket <ticket>`.
6. Перед релизом обязательно выполните `/qa <ticket>` или `claude-workflow qa --ticket <ticket> --report reports/qa/<ticket>.json --gate`, обновите QA-раздел tasklist и подтвердите прогресс `claude-workflow progress --source qa --ticket <ticket>`.
7. После отчётов QA/Review/Research сформируйте handoff-задачи для исполнителя: `claude-workflow tasks-derive --source <qa|review|research> --append --ticket <ticket>` добавит `- [ ]` с ссылками на отчёты в `docs/tasklist/<ticket>.md`; при необходимости подтвердите прогресс `claude-workflow progress --source handoff --ticket <ticket>`.

Детальный playbook агентов и барьеров описан в `docs/agents-playbook.md`.

## Слэш-команды

| Команда | Назначение | Аргументы (пример) |
| --- | --- | --- |
| `/idea-new` | Собрать вводные и автосоздать PRD (Status: draft → READY) | `STORE-123 checkout-discounts` |
| `/plan-new` | Подготовить план + валидацию | `checkout-discounts` |
| `/review-prd` | Провести ревью PRD и зафиксировать статус | `checkout-discounts` |
| `/tasks-new` | Обновить `docs/tasklist/<ticket>.md` по плану | `checkout-discounts` |
| `/implement` | Реализация по плану с автотестами | `checkout-discounts` |
| `/review` | Финальное ревью и фиксация статуса | `checkout-discounts` |
| `/qa` | Финальная QA-проверка, отчёт `reports/qa/<ticket>.json` | `checkout-discounts` |
| `claude-workflow progress` | Проверить наличие новых `- [x]` перед завершением шага | `--source implement --ticket checkout-discounts` |

## Режимы веток и коммитов

Конфигурация хранится в `config/conventions.json` и поддерживает три режима:

- **ticket-prefix** (по умолчанию): `feature/STORE-123` → `STORE-123: краткое описание`;
- **conventional**: `feat/orders` → `feat(orders): краткое описание`;
- **mixed**: `feature/STORE-123/feat/orders` → `STORE-123 feat(orders): краткое описание`.

Измените поле `commit.mode` вручную (`ticket-prefix`/`conventional`/`mixed`) и добавьте git-хук `commit-msg`, чтобы проверять сообщения — пример настроек в `docs/customization.md`.

## Выборочные тесты Gradle

Скрипт `.claude/hooks/format-and-test.sh`:
1. Собирает карту проектов через `.claude/gradle/init-print-projects.gradle` и кэширует её.
2. Анализирует `git diff` + незакоммиченные файлы, оставляя только влияющие на сборку артефакты.
3. Сопоставляет файлы с Gradle-модулями и формирует задачи вида `:module:clean :module:test`.
4. Подбирает fallback-задачи (`:jvmTest`, `:testDebugUnitTest`) и запускает общее `gradle test`, если модуль не определён.
5. Работает в «мягком» режиме — падение тестов не блокирует коммит (можно ужесточить в настройках).
6. Запускается автоматически после записей (`/implement`, ручные правки); чтобы временно отключить автозапуск, выставьте `SKIP_AUTO_TESTS=1`.

Подробности и советы по тройблшутингу собраны в `workflow.md` и `docs/customization.md`.

## Дополнительно
- Пошаговый пример использования и снимки до/после: `examples/apply-demo.sh` и раздел «Обзор этапов» в `workflow.md`.
- Подробный обзор цикла и гейтов: `workflow.md`.
- Playbook агентов и барьеров: `docs/agents-playbook.md`.
- Руководство по настройке `.claude/settings.json`, `config/conventions.json`, хуков и вспомогательных скриптов: `docs/customization.md`.
- Англоязычная версия README с правилами синхронизации: `README.en.md`.
- Демо-монорепо и скрипт применения: `examples/gradle-demo/`, `examples/apply-demo.sh`.
- Быстрая справка по слэш-командам: `.claude/commands/`.

## Миграция на agent-first
1. **Обновите репозиторий и payload.** Выполните `git pull`, затем `scripts/sync-payload.sh --direction=from-root && python3 tools/check_payload_sync.py`, чтобы новые шаблоны PRD/tasklist/research и команда `/idea-new` попали в проект и CLI payload.
2. **Обновите `.claude/agents|commands` и prompts.** Скопируйте свежие версии (RU/EN) в свой проект или переустановите workflow; убедитесь, что `templates/prompt-agent.md`/`prompt-command.md` совпадают, чтобы новые агенты сразу работали в стиле agent-first.
3. **Освежите активные тикеты.** Для каждой фичи выполните `claude-workflow research --ticket <ticket> --auto` (пересоберёт `reports/research/*.json` и шаблон research), затем `claude-workflow analyst-check --ticket <ticket>` — это подтвердит, что PRD и research соответствуют новым требованиям. При необходимости вручную перенесите разделы «Автоматизация»/«Команды» из обновлённых шаблонов в уже существующие артефакты.
4. **Проверьте тесты и гейты.** Запустите `scripts/ci-lint.sh` и smoke-сценарии (`scripts/smoke-workflow.sh`) — они проверят, что tasklist содержит новые поля `Reports/Commands`, а промпты не содержат устаревших `Answer N` инструкций.
5. **Документируйте миграцию.** Добавьте заметку в `docs/release-notes.md`/`CHANGELOG.md` вашего проекта, чтобы команда знала о новых правилах вопросов, логах команд и репозиторных источниках.

## Релизы CLI
- Версия берётся из `pyproject.toml`; пуш в `main` автоматически создаёт тег `v<версия>` (`.github/workflows/autotag.yml`), если такого ещё нет.
- Тег `v*` запускает workflow `release.yml`: собираются `sdist`/`wheel` (`python -m build`), артефакты прикрепляются к GitHub Release и сохраняются как artefact.
- Пользователи устанавливают CLI напрямую из репозитория: `uv tool install claude-workflow-cli --from git+https://github.com/GrinRus/ai_driven_dev.git` или `pipx install git+https://github.com/GrinRus/ai_driven_dev.git[@tag]`.
- Перед релизом обновляйте `CHANGELOG.md` и README, проверяйте `scripts/ci-lint.sh` и `claude-workflow smoke`. После релиза убедитесь, что релиз появился в разделе GitHub Releases и что указанные инструкции по установке актуальны.

## Вклад и лицензия
- Перед отправкой изменений ознакомьтесь с `CONTRIBUTING.md`.
- Лицензия проекта — MIT (`LICENSE`).
- Проект не аффилирован с поставщиками IDE/инструментов; используйте на свой риск.
