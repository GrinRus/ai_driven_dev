# Claude Code Workflow — Java/Kotlin Monorepo Template

> Готовый GitHub-шаблон и инсталлятор, который подключает Claude Code к вашему Java/Kotlin монорепозиторию, добавляет слэш-команды, безопасные хуки и выборочный запуск Gradle-тестов.

## TL;DR
- `/init-claude-workflow.sh` разворачивает многошаговый цикл `/idea-new → /plan-new → /tasks-new → /implement → /review` вместе с гейтами API/БД/тестов.
- Автоформат и выборочные Gradle-тесты запускаются после каждой правки (можно отключить `SKIP_AUTO_TESTS=1`), артефакты защищены хуками `gate-*`.
- Настраиваемые режимы веток/коммитов через `config/conventions.json` и готовые шаблоны документации.
- Опциональные интеграции с GitHub Actions, Issue/PR шаблонами и политиками доступа Claude Code.

## Оглавление
- [Что входит в шаблон](#что-входит-в-шаблон)
- [Архитектура workflow](#архитектура-workflow)
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
  - [Вариант A — curl](#вариант-a--curl)
  - [Вариант B — локально](#вариант-b--локально)
- [Предпосылки](#предпосылки)
- [Быстрый старт в Claude Code](#быстрый-старт-в-claude-code)
- [Чеклист запуска фичи](#чеклист-запуска-фичи)
- [Слэш-команды](#слэш-команды)
- [Режимы веток и коммитов](#режимы-веток-и-коммитов)
- [Выборочные тесты Gradle](#выборочные-тесты-gradle)
- [Дополнительно](#дополнительно)
- [Вклад и лицензия](#вклад-и-лицензия)

## Что входит в шаблон
- Слэш-команды Claude Code и саб-агенты для подготовки PRD/ADR/Tasklist, генерации документации и валидации коммитов.
- Многошаговый workflow (идея → план → валидация → задачи → реализация → ревью) с саб-агентами `analyst/planner/validator/implementer/reviewer` и дополнительными командами `/api-spec-new`, `/tests-generate`.
- Git-хуки для автоформатирования, запуска выборочных тестов и защиты продакшн-артефактов.
- Конфигурация коммитов (`ticket-prefix`, `conventional`, `mixed`) и вспомогательные скрипты CLI.
- Базовый набор документации, issue/PR шаблонов и CI workflow (включается флагом `--enable-ci`).
- Локальная, прозрачная установка без зависимости от Spec Kit или BMAD.

## Архитектура workflow
1. `init-claude-workflow.sh` разворачивает структуру `.claude/`, конфиги и шаблоны.
2. Slash-команды Claude Code запускают многошаговый процесс (см. `workflow.md`): от идеи и плана до реализации и ревью, подключая специализированных саб-агентов.
3. Пресет `strict` в `.claude/settings.json` включает гейты `gate-workflow`, `gate-api-contract`, `gate-db-migration`, `gate-tests` и автостарт `/test-changed` после каждой записи.
4. Git-хук `format-and-test.sh` выполняет форматирование и выборочные Gradle-тесты; полный прогон инициируется при изменении общих артефактов.
5. Политики доступа и режимы веток/коммитов управляются через `.claude/settings.json` и `config/conventions.json`.

Детали настройки и расширения описаны в `workflow.md` и `docs/customization.md`.

## Структура репозитория
| Каталог/файл | Назначение | Ключевые детали |
| --- | --- | --- |
| `.claude/settings.json` | Политики доступа и автоматизации | Пресеты `start`/`strict`, pre/post-хуки, auto-форматирование/тесты, защита prod-путей |
| `.claude/commands/` | Инструкция для слэш-команд | Маршруты `/idea-new`, `/plan-new`, `/tasks-new`, `/implement`, `/review` с `allowed-tools` и встроенными shell-шагами |
| `.claude/agents/` | Playbook саб-агентов | Роли `analyst`, `planner`, `validator`, `implementer`, `reviewer`, `api-designer`, `qa-author`, `db-migrator`, `contract-checker` |
| `.claude/hooks/` | Защитные и утилитарные хуки | `gate-workflow.sh`, `gate-api-contract.sh`, `gate-db-migration.sh`, `gate-tests.sh`, `protect-prod.sh`, `lint-deps.sh`, `format-and-test.sh` |
| `.claude/gradle/` *(создаётся при установке)* | Gradle-хелперы | `init-print-projects.gradle` объявляет задачу `ccPrintProjectDirs` для selective runner |
| `config/gates.json` | Параметры гейтов | Управляет `api_contract`, `db_migration`, `tests_required`, `deps_allowlist`, `feature_slug_source` |
| `config/conventions.json` | Режимы веток и коммитов | Расписаны шаблоны `ticket-prefix`, `conventional`, `mixed`, правила ветвления и ревью |
| `config/allowed-deps.txt` | Allowlist зависимостей | Формат `group:artifact`; предупреждения выводит `lint-deps.sh` |
| `doc/backlog.md` | План работ | Зафиксированные Wave 1/2 задачи и состояние их выполнения |
| `docs/` | Руководства и шаблоны | `usage-demo.md`, `customization.md`, `agents-playbook.md`, `release-notes.md`, шаблоны PRD/ADR/tasklist, рабочие артефакты фич |
| `examples/` | Демо-материалы | Сценарий `apply-demo.sh`, заготовка Gradle-монорепо `gradle-demo/` |
| `scripts/` | CLI и вспомогательные сценарии | `ci-lint.sh` (линтеры + тесты), `smoke-workflow.sh` (E2E smoke сценарий gate-workflow) |
| `templates/` | Шаблоны вендорных артефактов | Git-хуки (`commit-msg`, `pre-push`, `prepare-commit-msg`) и расширенный `tasklist.md` |
| `tests/` | Python-юнит-тесты | Проверяют init-скрипт, хуки, selective tests и настройки доступа |
| `.github/workflows/ci.yml` | CI pipeline | Запускает `scripts/ci-lint.sh`, ставит `shellcheck`, `markdownlint`, `yamllint` |
| `init-claude-workflow.sh` | Bootstrap-скрипт | Флаги `--commit-mode`, `--enable-ci`, `--force`, `--dry-run`, проверка зависимостей и генерация структуры |
| `workflow.md` | Процессная документация | Детальный сценарий idea → plan → tasks → implement → review |
| `claude-workflow-extensions.patch` | Пакет расширений | Diff с дополнительными агентами, гейтами и командами для продвинутых установок |
| `README.en.md` | Англоязычный README | Синхронизируется с этой версией, содержит пометку _Last sync_ |
| `CONTRIBUTING.md` | Правила вкладов | Описывает процесс PR/issue, требования к коммитам и линтингу |
| `LICENSE` | Лицензия | MIT с ограничениями ответственности |

> `init-claude-workflow.sh` генерирует CLI (`scripts/commit_msg.py`, `scripts/branch_new.py`, `scripts/conventions_set.py`) и `.claude/gradle/init-print-projects.gradle`. Скрипты уже находятся в репозитории и обновляются при переустановке, поэтому команды `/commit`, `/branch-new`, `/conventions-set` готовы к использованию сразу после bootstrap.

## Детальный анализ компонентов

### Скрипты установки и утилиты
- `init-claude-workflow.sh` — модульный bootstrap со строгими проверками (`bash/git/python3`, Gradle/ktlint), режимами `--commit-mode/--enable-ci/--force/--dry-run`, генерацией `.claude/`, `config/`, `docs/`, `templates/`, `.gitkeep` и CLI-скриптов, а также автоматическим обновлением `config/conventions.json`.
- `scripts/ci-lint.sh` — единая точка для `shellcheck`, `markdownlint`, `yamllint` и `python -m unittest`, интегрированная с CI и корректно пропускающая отсутствующие линтеры с предупреждением.
- `scripts/smoke-workflow.sh` — E2E smoke-сценарий: поднимает временный проект, запускает bootstrap, воспроизводит slug → PRD → план → tasklist и убеждается, что `gate-workflow.sh` корректно блокирует/разрешает правки.
- `examples/apply-demo.sh` — демонстрирует применение шаблона к Gradle-монорепо, печатает дерево каталогов до/после и, при наличии wrapper, запускает `gradlew test`.
- CLI, генерируемые bootstrap-скриптом (`scripts/commit_msg.py`, `scripts/branch_new.py`, `scripts/conventions_set.py`) — формируют сообщения коммитов, создают ветки по пресетам и позволяют вручную переключать commit-mode.

### Git-хуки и автоматизация
- `.claude/hooks/format-and-test.sh` — Python-хук, который читает `.claude/settings.json`, учитывает `SKIP_FORMAT`, `FORMAT_ONLY`, `TEST_SCOPE`, `STRICT_TESTS`, `SKIP_AUTO_TESTS`, анализирует `git diff`, slug из `docs/.active_feature`, умеет переключать selective/full run и подбирает задачи через `moduleMatrix`, `defaultTasks`, `fallbackTasks`.
- `.claude/hooks/gate-workflow.sh` — блокирует правки под `src/**`, если для активного slug нет PRD, плана или чекбоксов в `tasklist.md`, игнорирует изменения в документации/шаблонах.
- `.claude/hooks/gate-api-contract.sh`, `gate-db-migration.sh`, `gate-tests.sh` — гейты `config/gates.json`: контролируют наличие OpenAPI (yaml/json), миграций Flyway/Liquibase (tracked + untracked), соответствующих тестов (`soft/hard/disabled`) и возвращают подсказки по разблокировке.
- `.claude/hooks/protect-prod.sh` и `lint-deps.sh` — защищают продакшн-пути (`infra/prod/**`, `deploy/prod/**`), уважают `PROTECT_PROD_BYPASS`/`PROTECT_LOG_ONLY`, проверяют allowlist `config/allowed-deps.txt` и анализируют diff Gradle-файлов.
- `.claude/gradle/init-print-projects.gradle` — вспомогательный скрипт, регистрирует задачу `ccPrintProjectDirs` для построения кеша модулей selective runner.

### Саб-агенты Claude Code
- `.claude/agents/analyst.md` — формализует идею в PRD со статусом READY/BLOCKED, задаёт уточняющие вопросы, фиксирует риски/допущения и обновляет `docs/prd/<slug>.prd.md`.
- `.claude/agents/planner.md` — строит пошаговый план (`docs/plan/<slug>.md`) с DoD и зависимостями; `.claude/agents/validator.md` проверяет план и записывает вопросы для продуктов/архитекторов.
- `.claude/agents/implementer.md` — ведёт реализацию малыми итерациями, требует запуск `/test-changed`, отслеживает гейты и синхронизацию с tasklist.
- `.claude/agents/reviewer.md` — оформляет код-ревью, проверяет чеклисты, ставит статусы READY/BLOCKED и фиксирует follow-up в `tasklist.md`.
- `.claude/agents/api-designer.md` — готовит/обновляет `docs/api/<slug>.yaml`, описывает CRUD/edge-cases, error schema и outstanding questions.
- `.claude/agents/qa-author.md` — генерирует юнит/интеграционные тесты, `docs/test/<slug>-manual.md`, запускает `/test-changed` и оставляет отчёт о покрытии.
- `.claude/agents/db-migrator.md` — формирует миграции Flyway/Liquibase (`db/migration/V<timestamp>__<slug>.sql`, changelog) и отмечает ручные шаги/зависимости.
- `.claude/agents/contract-checker.md` — сравнивает контроллеры с OpenAPI, выявляет лишние/отсутствующие эндпоинты, статусы и поля, формирует actionable summary.

### Слэш-команды и пайплайн
- `.claude/commands/feature-activate.md` — выставляет slug в `docs/.active_feature`, активирует workflow-гейты.
- `.claude/commands/branch-new.md` — использует `scripts/branch_new.py`, создаёт ветки (`feature/`, `feat/`, `hotfix/`, `mixed`) и возвращает итоговое имя.
- `.claude/commands/idea-new.md` — вызывает `analyst`, создаёт PRD, фиксирует открытые вопросы и slug.
- `.claude/commands/plan-new.md` — подключает `planner` и `validator`, обновляет план и протокол проверки.
- `.claude/commands/tasks-new.md` — синхронизирует `tasklist.md` с планом, распределяя задачи по этапам и slug.
- `.claude/commands/api-spec-new.md` — поручает `api-designer` собрать OpenAPI и подсветить outstanding вопросы.
- `.claude/commands/tests-generate.md` — активирует `qa-author` для автогенерации тестов и ручных сценариев.
- `.claude/commands/implement.md` — фиксирует шаги реализации, напоминает про гейты и автоматические тесты.
- `.claude/commands/review.md` — оформляет ревью, обновляет чеклисты и статус READY/BLOCKED.
- `.claude/commands/commit.md` и `commit-validate.md` — используют `scripts/commit_msg.py` для формирования/валидации сообщений в активном режиме `config/conventions.json`.
- `.claude/commands/test-changed.md` — тонкая настройка `format-and-test.sh`, запускает selective Gradle задачи, умеет передавать кастомный scope.

### Конфигурация и политики
- `.claude/settings.json` — пресеты `start/strict`, списки `allow/ask/deny`, pre/post-хуки, параметры `automation` (формат/тесты) и `protection` с переменными `PROTECT_PROD_BYPASS`/`PROTECT_LOG_ONLY`.
- `config/conventions.json` — commit/branch режимы (`ticket-prefix`, `conventional`, `mixed`), шаблоны сообщений, примеры, заметки для ревью и CLI.
- `config/gates.json` — флаги `api_contract`, `db_migration`, `tests_required`, `deps_allowlist`, `feature_slug_source`; управляет поведением гейтов и `lint-deps.sh`.
- `config/allowed-deps.txt` — allowlist `group:artifact`, поддерживает комментарии, используется `lint-deps.sh`.

### Документация и шаблоны
- `workflow.md`, `docs/customization.md`, `docs/usage-demo.md`, `docs/agents-playbook.md` — описывают процесс idea→review, walkthrough установки, настройку `.claude/settings.json` и роли саб-агентов.
- `docs/prd.template.md`, `docs/adr.template.md`, `docs/tasklist.template.md`, `templates/tasklist.md` — шаблоны с подсказками, чеклистами, секциями истории изменений и примерами заполнения.
- `templates/git-hooks/*.sample`, `templates/git-hooks/README.md` — готовые `commit-msg`, `prepare-commit-msg`, `pre-push` с инструкциями, переменными окружения и советами по развёртыванию.
- `doc/backlog.md`, `docs/release-notes.md` — wave-бэклог (Wave 1/2) и регламент релизов, помогают планировать roadmap и управлять changelog.

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
- Инициализация (`init-claude-workflow.sh`) генерирует настройки `.claude/settings.json`, гейты и CLI, которые затем вызываются слэш-командами и hook-пайплайном.
- Пресет `strict` в `.claude/settings.json` подключает pre/post-хуки, автоматически запускает `.claude/hooks/format-and-test.sh` после успешной записи и привязывает защиту продовых путей.
- Гейты (`gate-*`) читают `config/gates.json` и артефакты в `docs/**`, обеспечивая прохождение цепочки `/idea-new → /plan-new → /tasks-new`; команды `/api-spec-new` и `/tests-generate` активируют саб-агентов и разблокируют критичные пути.
- `.claude/hooks/format-and-test.sh` опирается на Gradle-скрипт `init-print-projects.gradle`, slug в `docs/.active_feature` и `moduleMatrix`, чтобы решать, запускать ли selective или полный набор задач.
- Тестовый набор на Python использует `tests/helpers.py` для эмуляции git/файловой системы, покрывая dry-run, tracked/untracked изменения и поведение хуков.

## Ключевые скрипты и хуки
- **`init-claude-workflow.sh`** — валидирует `bash/git/python3`, ищет Gradle/kotlin-линтеры, генерирует каталоги `.claude/ config/ docs/ templates/`, перезаписывает артефакты по `--force`, выводит dry-run и настраивает режим коммитов.
- **`.claude/hooks/format-and-test.sh`** — анализирует `git diff`, собирает задачи из `automation.tests` (`changedOnly`, `moduleMatrix`), уважает `SKIP_FORMAT`, `FORMAT_ONLY`, `TEST_SCOPE`, `STRICT_TESTS`, `SKIP_AUTO_TESTS` и умеет подстраивать полный прогон при изменении общих файлов.
- **`gate-workflow.sh`** — блокирует изменения в `src/**`, пока не создана цепочка PRD/план/tasklist для активной фичи (`docs/.active_feature`); проверяет чекбоксы `tasklist.md`.
- **`gate-api-contract.sh` / `gate-db-migration.sh` / `gate-tests.sh`** — требуют наличие OpenAPI (`docs/api/<slug>.yaml`), миграций в `src/main/resources/**/db/migration/` и тестов `src/test/**`, учитывая режимы `config/gates.json`.
- **`protect-prod.sh` и `lint-deps.sh`** — защищают продовые пути (`infra/prod/**`, `deploy/prod/**`), поддерживают allowlist зависимостей `config/allowed-deps.txt` и поддерживают bypass/log-only переменные окружения.
- **`scripts/ci-lint.sh`** — единая точка для `shellcheck`, `markdownlint`, `yamllint` и `python -m unittest`, используется локально и в GitHub Actions.
- **`scripts/smoke-workflow.sh`** — поднимает временной проект, гоняет init-скрипт и проверяет прохождение `gate-workflow` по шагам `/idea-new → /plan-new → /tasks-new`.
- **`examples/apply-demo.sh`** — пошагово применяет шаблон к директории с Gradle-модулями, демонстрируя интеграцию с `gradlew`.

## Тестовый контур
- `tests/helpers.py` — вспомогательные функции (создание файлов, git init/config, запуск хуков) для изоляции сценариев.
- `tests/test_init_claude_workflow.py` — проверяет чистую установку, `--dry-run`, `--force`, наличие ключевых артефактов и поведение bootstrap-скрипта.
- `tests/test_gate_*.py` — проверяют workflow/API/DB/tests гейты: учитывают slug, tracked/untracked миграции, режимы `soft/hard/disabled` и нецелевые файлы.
- `tests/test_format_and_test.py` — моделирует запуск Python-хука, проверяет `moduleMatrix`, реакцию на общие файлы, переменные `SKIP_AUTO_TESTS`, `TEST_SCOPE`.
- `tests/test_settings_policy.py` — валидирует `.claude/settings.json`, гарантируя, что критичные команды (`git add/commit/push`, `curl`, запись в прод-пути) находятся в `ask/deny`.
- `scripts/ci-lint.sh` и `.github/workflows/ci.yml` — единый entrypoint линтеров/тестов для локального запуска и GitHub Actions.
- `scripts/smoke-workflow.sh` — E2E smoke, подтверждает, что `gate-workflow` блокирует исходники до появления PRD/плана/tasklist.

## Диагностика и отладка
- **Линтеры и тесты:** запускайте `scripts/ci-lint.sh` для полного набора (`shellcheck`, `markdownlint`, `yamllint`, `python -m unittest`) или адресно `python3 -m unittest tests/test_gate_workflow.py`.
- **Переменные окружения:** `SKIP_AUTO_TESTS`, `SKIP_FORMAT`, `FORMAT_ONLY`, `TEST_SCOPE`, `TEST_CHANGED_ONLY`, `STRICT_TESTS` управляют `.claude/hooks/format-and-test.sh`; `PROTECT_PROD_BYPASS` и `PROTECT_LOG_ONLY` ослабляют `protect-prod.sh`.
- **Диагностика гейтов:** передайте payload через stdin: `echo '{"tool_input":{"file_path":"src/main/kotlin/App.kt"}}' | CLAUDE_PROJECT_DIR=$PWD .claude/hooks/gate-workflow.sh`.
- **Selective runner:** пересоздайте карту модулей `./gradlew -I .claude/gradle/init-print-projects.gradle ccPrintProjectDirs`, проверьте `.claude/cache/project-dirs.txt`.
- **Smoke-сценарий:** `scripts/smoke-workflow.sh` поднимет временной проект и проверит последовательность `/idea-new → /plan-new → /tasks-new`.
- **CI-проверки:** GitHub Actions (`.github/workflows/ci.yml`) ожидает установленные `shellcheck`, `yamllint`, `markdownlint`; убедитесь, что локальная среда воспроизводит их версии при отладке.

## Политики доступа и гейты
- `.claude/settings.json` содержит пресеты `start` и `strict`: первый позволяет базовые операции, второй включает pre- и post-хуки (`protect-prod`, `gate-*`, `format-and-test`, `lint-deps`) и требует явного подтверждения `git add/commit/push`.
- Раздел `automation` управляет форматированием и тестами, а `protection` задаёт сохранность продовых артефактов с поддержкой `PROTECT_PROD_BYPASS` и `PROTECT_LOG_ONLY`.
- `config/gates.json` централизует флаги `api_contract`, `db_migration`, `tests_required` и `deps_allowlist`, а также путь к активной фиче (`feature_slug_source`).
- Комбинация хуков `gate-*` в `.claude/hooks/` реализует согласованную политику: блокировка кода без артефактов, требование миграций и тестов, контроль API-контрактов.

## Документация и шаблоны
- `workflow.md`, `docs/agents-playbook.md` — описывают целевой цикл idea→review, роли саб-агентов и взаимодействие с гейтами.
- `docs/usage-demo.md`, `docs/customization.md` — walkthrough применения bootstrap к Gradle-монорепо и подробности настройки `.claude/settings.json`, гейтов, шаблонов команд.
- `docs/release-notes.md`, `doc/backlog.md` — регламент релизов и wave-бэклог (Wave 1/2) для планирования roadmap.
- Шаблоны PRD/ADR/tasklist (`docs/*.template.md`, `templates/tasklist.md`) и git-хуки (`templates/git-hooks/*.sample`) — расширенные заготовки с подсказками, чеклистами и переменными окружения.
- `README.en.md` — синхронизированный перевод; при правках обновляйте обе версии и поле Last sync.

## Примеры и демо
- `examples/gradle-demo/` — двухсервисный Gradle-монорепо (Kotlin 1.9.22, `jvmToolchain(17)`, JUnit 5), демонстрирующий структуру модулей и пригодный для selective тестов.
- `examples/apply-demo.sh` — пошаговый сценарий применения bootstrap к демо-проекту, полезен для воркшопов и презентаций.
- `scripts/smoke-workflow.sh` + `docs/usage-demo.md` — живой пример: скрипт автоматизирует установку и прохождение гейтов, документация описывает ожидаемые результаты и советы по отладке.

## Незакрытые задачи и наблюдения
- `doc/backlog.md` хранит Wave 2 пункты, среди которых возврат CLI (`scripts/commit_msg.py`, `scripts/branch_new.py`, `scripts/conventions_set.py`) и Gradle-хелпера в репозиторий после генерации.
- `claude-workflow-extensions.patch` расширяет агентов/команды; применяйте его вручную и фиксируйте конфликты, если используете дополнительные гейты.
- Собирая новый монорепо, переносите сгенерированные CLI и `.claude/gradle/init-print-projects.gradle` под контроль версий — smoke/CI тесты ожидают их наличия.
- Следите за синхронизацией `README.en.md` (метка _Last sync_) после обновлений документации.

## Установка

### Вариант A — `curl`

> Замените `<your-org>/<repo>` на репозиторий, где размещён `init-claude-workflow.sh`.

```bash
curl -fsSL https://raw.githubusercontent.com/<your-org>/<repo>/main/init-claude-workflow.sh \
  | bash -s -- --commit-mode ticket-prefix --enable-ci
```

### Вариант B — локально

1. Сохраните `init-claude-workflow.sh` в корень проекта.
2. Выполните:

```bash
bash init-claude-workflow.sh --commit-mode ticket-prefix --enable-ci
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
- Gradle wrapper (`./gradlew`) или установленный Gradle;
- (опционально) `ktlint` и/или Spotless для автоформатирования.

Поддерживаются macOS/Linux. На Windows используйте WSL или Git Bash.

## Быстрый старт в Claude Code

Откройте проект в Claude Code и выполните команды:

```
/branch-new feature STORE-123
/feature-activate checkout-discounts
/idea-new checkout-discounts STORE-123
/plan-new checkout-discounts
/tasks-new checkout-discounts
/api-spec-new checkout-discounts
/tests-generate checkout-discounts
/implement checkout-discounts
/review checkout-discounts
```

Результат:
- создаётся цепочка артефактов (PRD, план, tasklist, OpenAPI, тесты);
- при правках автоматически запускается `/test-changed`, гейты блокируют изменения без контрактов/миграций/тестов;
- `/commit` и `/review` работают в связке с чеклистами, помогая довести фичу до статуса READY.

## Чеклист запуска фичи

1. Создайте ветку (`/branch-new` или вручную) и активируйте slug через `/feature-activate <slug>`.
2. Соберите артефакты аналитики: `/idea-new`, `/plan-new`, `/tasks-new` до статуса READY/PASS.
3. Подготовьте интеграции и данные: `/api-spec-new`, запустите `contract-checker`, при необходимости вызовите агента `db-migrator`.
4. Закройте тестовый контур: `/tests-generate`, убедитесь, что `gate-tests` не выдаёт предупреждений/блокировок.
5. Реализуйте фичу малыми шагами через `/implement`, отслеживая сообщения `gate-workflow`, `gate-api-contract`, `gate-db-migration`.
6. Запросите `/review`, когда чеклисты в `tasklist.md` закрыты, тесты зелёные и артефакты синхронизированы.

Детальный playbook агентов и барьеров описан в `docs/agents-playbook.md`.

## Слэш-команды

| Команда | Назначение | Аргументы (пример) |
|---|---|---|
| `/branch-new` | Создать/переключить ветку по пресету | `feature STORE-123` / `feat orders` / `mixed STORE-123 feat pricing` |
| `/feature-activate` | Зафиксировать slug активной фичи | `checkout-discounts` |
| `/idea-new` | Собрать вводные и оформить PRD | `checkout-discounts STORE-123` |
| `/plan-new` | Подготовить план + валидацию | `checkout-discounts` |
| `/tasks-new` | Обновить `tasklist.md` по плану | `checkout-discounts` |
| `/implement` | Реализация по плану с автотестами | `checkout-discounts` |
| `/review` | Финальное ревью и фиксация статуса | `checkout-discounts` |
| `/api-spec-new` | Создать/обновить OpenAPI контракт | `checkout-discounts` |
| `/tests-generate` | Сгенерировать юнит/интеграционные тесты | `checkout-discounts` |
| `/test-changed` | Прогнать выборочные Gradle-тесты | — |
| `/conventions-set` | Сменить режим коммитов | `conventional` / `ticket-prefix` / `mixed` |
| `/conventions-sync` | Синхронизировать `conventions.md` с Gradle-конфигами | — |
| `/commit` | Сформировать и сделать коммит | `"implement rule engine"` |
| `/commit-validate` | Проверить сообщение коммита на соответствие режиму | `"feat(orders): add x"` |

## Режимы веток и коммитов

Конфигурация хранится в `config/conventions.json` и поддерживает три режима:

- **ticket-prefix** (по умолчанию): `feature/STORE-123` → `STORE-123: краткое описание`;
- **conventional**: `feat/orders` → `feat(orders): краткое описание`;
- **mixed**: `feature/STORE-123/feat/orders` → `STORE-123 feat(orders): краткое описание`.

Смена режима выполняется командой:

```text
/conventions-set conventional
```

Для обязательной проверки сообщений коммитов добавьте git-хук `commit-msg` — пример в `docs/customization.md`.

## Выборочные тесты Gradle

Скрипт `.claude/hooks/format-and-test.sh`:
1. Собирает карту проектов через `.claude/gradle/init-print-projects.gradle` и кэширует её.
2. Анализирует `git diff` + незакоммиченные файлы, оставляя только влияющие на сборку артефакты.
3. Сопоставляет файлы с Gradle-модулями и формирует задачи вида `:module:clean :module:test`.
4. Подбирает fallback-задачи (`:jvmTest`, `:testDebugUnitTest`) и запускает общее `gradle test`, если модуль не определён.
5. Работает в «мягком» режиме — падение тестов не блокирует коммит (можно ужесточить в настройках).
6. Запускается автоматически после записей (`/implement`, ручные правки); чтобы временно отключить автозапуск, выставьте `SKIP_AUTO_TESTS=1`.

Подробности и советы по тройблшутингу собраны в `docs/usage-demo.md` и `docs/customization.md`.

## Дополнительно
- Пошаговый пример использования и снимки до/после: `docs/usage-demo.md`.
- Подробный обзор цикла и гейтов: `workflow.md`.
- Playbook агентов и барьеров: `docs/agents-playbook.md`.
- Руководство по настройке `.claude/settings.json`, `config/conventions.json`, хуков и CLI: `docs/customization.md`.
- Англоязычная версия README с правилами синхронизации: `README.en.md`.
- Демо-монорепо и скрипт применения: `examples/gradle-demo/`, `examples/apply-demo.sh`.
- Быстрая справка по слэш-командам: `.claude/commands/`.

## Вклад и лицензия
- Перед отправкой изменений ознакомьтесь с `CONTRIBUTING.md`.
- Лицензия проекта — MIT (`LICENSE`).
- Проект не аффилирован с поставщиками IDE/инструментов; используйте на свой риск.
