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
- [Ключевые скрипты и хуки](#ключевые-скрипты-и-хуки)
- [Тестовый контур](#тестовый-контур)
- [Политики доступа и гейты](#политики-доступа-и-гейты)
- [Документация и шаблоны](#документация-и-шаблоны)
- [Примеры и демо](#примеры-и-демо)
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

## Детальный анализ компонентов

### Скрипты установки и утилиты
- `init-claude-workflow.sh` — модульный bootstrap с проверкой зависимостей, режимами `--commit-mode/--enable-ci/--force/--dry-run`, созданием `.claude/`, `config/`, `docs/`, `templates/` и обновлением `config/conventions.json`.
- `scripts/ci-lint.sh` — единый запуск `shellcheck`, `markdownlint`, `yamllint` и `python -m unittest`, который используется локально и в CI.
- `scripts/smoke-workflow.sh` — интеграционный smoke-тест `gate-workflow.sh`, эмулирует последовательность slug → PRD → план → tasklist.
- `examples/apply-demo.sh` — копирует Gradle-монорепо из `examples/gradle-demo/`, запускает bootstrap и демонстрирует selective Gradle-тесты.

### Git-хуки и автоматизация
- `.claude/hooks/format-and-test.sh` — Python-хук, который читает `.claude/settings.json`, поддерживает флаги `SKIP_FORMAT`, `FORMAT_ONLY`, `TEST_SCOPE`, `STRICT_TESTS`, анализирует `git diff` и решает, запускать выборочные или полные задачи.
- `.claude/hooks/gate-workflow.sh` — блокирует правки под `src/**`, если для активного slug нет PRD, плана или записей в `tasklist.md`.
- `.claude/hooks/gate-api-contract.sh`, `gate-db-migration.sh`, `gate-tests.sh` — гейты, завязанные на `config/gates.json`: проверяют наличие OpenAPI, миграций и тестов с учётом режимов `soft/hard/disabled`.
- `.claude/hooks/protect-prod.sh` и `lint-deps.sh` — защищают продакшн-пути и подсвечивают зависимости вне allowlist, учитывая переменные окружения и кастомные исключения.

### Саб-агенты Claude Code
- `.claude/agents/analyst.md` — формализует идею в PRD со статусом READY/BLOCKED, задаёт уточняющие вопросы и фиксирует риски.
- `.claude/agents/planner.md` — строит по PRD пошаговый план (`docs/plan/<slug>.md`) с DoD и ссылками на модули.
- `.claude/agents/validator.md` — сверяет PRD/план по списку критериев и возвращает PASS/FAIL с конкретными вопросами.
- `.claude/agents/implementer.md` — ведёт реализацию малыми итерациями, требует запуск `/test-changed` и опирается на план.
- `.claude/agents/reviewer.md` — оформляет ревью: проверяет код против чеклистов, фиксирует замечания и статус готовности.
- `.claude/agents/api-designer.md` — готовит/обновляет `docs/api/<slug>.yaml`, перечисляет неясные контракты и примеры.
- `.claude/agents/qa-author.md` — генерирует юнит/интеграционные тесты и `docs/test/<slug>-manual.md`.
- `.claude/agents/db-migrator.md` — описывает миграции, создаёт заготовки `db/migration/V<timestamp>__<slug>.sql` и ручные шаги.
- `.claude/agents/contract-checker.md` — сравнивает контроллеры с OpenAPI, возвращает дифф и подсказки по синхронизации.

### Слэш-команды и пайплайн
- `.claude/commands/feature-activate.md` — выставляет slug в `docs/.active_feature`, запускает гейты для конкретной фичи.
- `.claude/commands/idea-new.md` — вызывает `analyst`, создаёт PRD и список открытых вопросов.
- `.claude/commands/plan-new.md` — связывает `planner` и `validator`, обновляет план и протокол проверки.
- `.claude/commands/tasks-new.md` — обновляет `tasklist.md` и чеклисты, синхронизируя их со свежим планом.
- `.claude/commands/api-spec-new.md` — поручает `api-designer` собрать OpenAPI и подсветить непокрытые эндпоинты.
- `.claude/commands/tests-generate.md` — активирует `qa-author` для автогенерации тестов и ручных сценариев.
- `.claude/commands/implement.md` — упрощает цикл реализации: фиксирует шаги, напоминает про автотесты и гейты.
- `.claude/commands/review.md` — оформляет ревью и статусы READY/BLOCKED, проверяет чеклисты.
- `.claude/commands/commit.md` и `commit-validate.md` — помогают собрать сообщение коммита в активном режиме `config/conventions.json`.
- `.claude/commands/test-changed.md` — тонкая настройка `format-and-test.sh`, запускает selective Gradle задачи.

### Конфигурация и политики
- `.claude/settings.json` — два пресета (`start`, `strict`), список разрешённых/запрашиваемых команд, pre/post-хуки и параметры автоматизации (`automation.format/tests`, `protection`).
- `config/conventions.json` — описание commit/branch режимов (`ticket-prefix`, `conventional`, `mixed`), вспомогательных полей и рекомендаций для ревью.
- `config/gates.json` — флаги `api_contract`, `db_migration`, `tests_required`, `deps_allowlist` и путь к активной фиче (`feature_slug_source`).
- `config/allowed-deps.txt` — плоский allowlist `group:artifact`, который использует `lint-deps.sh`.

### Документация и шаблоны
- `workflow.md`, `docs/customization.md`, `docs/usage-demo.md`, `docs/agents-playbook.md` — руководства по процессу, настройке, демонстрациям и ролям саб-агентов.
- `docs/prd.template.md`, `docs/adr.template.md`, `docs/tasklist.template.md`, `templates/tasklist.md` — расширенные шаблоны артефактов с подсказками и чеклистами.
- `templates/git-hooks/*.sample` и `templates/git-hooks/README.md` — готовые `commit-msg`, `prepare-commit-msg`, `pre-push` с инструкциями по установке.
- `doc/backlog.md` и `docs/release-notes.md` — wave-бэклог и регламент релизов для планирования дальнейших итераций.

### Тесты и контроль качества
- `tests/test_init_claude_workflow.py` — проверка bootstrap-скрипта, флагов `--dry-run` и `--force`.
- `tests/test_gate_*.py` — сценарии для гейтов workflow, API, миграций БД и обязательных тестов.
- `tests/test_format_and_test.py` — тесты selective runner с матрицей модулей и переменными окружения.
- `tests/test_settings_policy.py` — защита `permissions`/`hooks` в `.claude/settings.json`.

### Демо и расширения
- `examples/gradle-demo/` — двухсервисный Gradle-монорепо для проверки selective тестов и интеграции.
- `claude-workflow-extensions.patch` — patch-файл с расширениями агентов, команд и гейтов, пригодный для применения к чистому репозиторию.

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
- `tests/test_init_claude_workflow.py` проверяет чистую установку, `--dry-run` (без побочных эффектов) и `--force` (перезапись артефактов).
- `tests/test_gate_*.py` покрывают гейты: workflow (PRD/план/tasklist), API контракт, миграции БД (учитывая tracked/untracked файлы), обязательные тесты в `soft/hard` режимах.
- `tests/test_format_and_test.py` моделирует запуск Python-хука, проверяет `moduleMatrix`, реакцию на общие файлы и переменные `SKIP_AUTO_TESTS`, `TEST_SCOPE`.
- `tests/test_settings_policy.py` валидирует `.claude/settings.json`, гарантируя, что критичные команды (`git add/commit/push`, `curl`, prod-пути) находятся в `ask/deny`.
- `scripts/ci-lint.sh` и `.github/workflows/ci.yml` запускают линтеры + юнит-тесты, обеспечивая единый entrypoint для локальных и CI-проверок.
- `scripts/smoke-workflow.sh` выполняет E2E smoke, подтверждая, что `gate-workflow` корректно блокирует исходники до появления артефактов.

## Политики доступа и гейты
- `.claude/settings.json` содержит пресеты `start` и `strict`: первый позволяет базовые операции, второй включает pre- и post-хуки (`protect-prod`, `gate-*`, `format-and-test`, `lint-deps`) и требует явного подтверждения `git add/commit/push`.
- Раздел `automation` управляет форматированием и тестами, а `protection` задаёт сохранность продовых артефактов с поддержкой `PROTECT_PROD_BYPASS` и `PROTECT_LOG_ONLY`.
- `config/gates.json` централизует флаги `api_contract`, `db_migration`, `tests_required` и `deps_allowlist`, а также путь к активной фиче (`feature_slug_source`).
- Комбинация хуков `gate-*` в `.claude/hooks/` реализует согласованную политику: блокировка кода без артефактов, требование миграций и тестов, контроль API-контрактов.

## Документация и шаблоны
- `workflow.md` описывает полный цикл идея→план→таски→реализация→ревью, а `docs/agents-playbook.md` даёт роли и выходы агентов.
- `docs/usage-demo.md` показывает установку на Gradle-монорепо, `docs/customization.md` детализирует настройку `.claude/settings.json`, гейтов и шаблонов команд.
- `docs/release-notes.md` и `doc/backlog.md` фиксируют процесс версионирования и историю задач (Wave 1/2).
- Шаблоны PRD/ADR/tasklist (`docs/*.template.md`, `templates/tasklist.md`) и git-хуки (`templates/git-hooks/*.sample`) упрощают адаптацию под команды.
- `README.en.md` хранит синхронизированный перевод; при правках обновляйте обе версии и поле Last sync.

## Примеры и демо
- `examples/gradle-demo/` — каркас монорепозитория с модулями `service-checkout` и `service-payments`, демонстрирующий структуру модулей.
- `examples/apply-demo.sh` — сценарий применения init-скрипта к демо-проекту, полезен для презентаций/воркшопов.
- `scripts/smoke-workflow.sh` и `docs/usage-demo.md` образуют «живой» пример: скрипт автоматизирует шаги, документация даёт пошаговый walkthrough и ожидаемые результаты.

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
/feature-new checkout-discounts STORE-123
/feature-adr checkout-discounts
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
| `/feature-new` | Создать PRD и стартовые артефакты | `checkout-discounts STORE-123` |
| `/feature-adr` | Сформировать ADR из PRD | `checkout-discounts` |
| `/plan-new` | Подготовить план + валидацию | `checkout-discounts` |
| `/tasks-new` | Обновить `tasklist.md` по плану | `checkout-discounts` |
| `/implement` | Реализация по плану с автотестами | `checkout-discounts` |
| `/review` | Финальное ревью и фиксация статуса | `checkout-discounts` |
| `/api-spec-new` | Создать/обновить OpenAPI контракт | `checkout-discounts` |
| `/tests-generate` | Сгенерировать юнит/интеграционные тесты | `checkout-discounts` |
| `/docs-generate` | Сгенерировать/обновить документацию | — |
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
