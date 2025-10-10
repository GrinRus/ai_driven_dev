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
- [Установка](#установка)
  - [Вариант A — curl](#вариант-a--curl)
  - [Вариант B — локально](#вариант-b--локально)
- [Предпосылки](#предпосылки)
- [Быстрый старт в Claude Code](#быстрый-старт-в-claude-code)
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
- Руководство по настройке `.claude/settings.json`, `config/conventions.json`, хуков и CLI: `docs/customization.md`.
- Англоязычная версия README с правилами синхронизации: `README.en.md`.
- Демо-монорепо и скрипт применения: `examples/gradle-demo/`, `examples/apply-demo.sh`.
- Быстрая справка по слэш-командам: `.claude/commands/`.

## Вклад и лицензия
- Перед отправкой изменений ознакомьтесь с `CONTRIBUTING.md`.
- Лицензия проекта — MIT (`LICENSE`).
- Проект не аффилирован с поставщиками IDE/инструментов; используйте на свой риск.
