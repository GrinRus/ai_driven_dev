# Claude Code Workflow — Java/Kotlin Monorepo Template

> Готовый GitHub-шаблон и инсталлятор, который подключает Claude Code к вашему Java/Kotlin монорепозиторию, добавляет слэш-команды, безопасные хуки и выборочный запуск Gradle-тестов.

## TL;DR
- `/init-claude-workflow.sh` настраивает слэш-команды Claude Code (PRD → ADR → Tasks → Docs) и git-хуки за один проход.
- Автоматический запуск только затронутых Gradle-модулей и мягкие проверки формата (Spotless/ktlint, если доступны).
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
- Git-хуки для автоформатирования, запуска выборочных тестов и защиты продакшн-артефактов.
- Конфигурация коммитов (`ticket-prefix`, `conventional`, `mixed`) и вспомогательные скрипты CLI.
- Базовый набор документации, issue/PR шаблонов и CI workflow (включается флагом `--enable-ci`).
- Локальная, прозрачная установка без зависимости от Spec Kit или BMAD.

## Архитектура workflow
1. `init-claude-workflow.sh` разворачивает структуру `.claude/`, конфиги и шаблоны.
2. Claude Code использует slash-команды, которые взаимодействуют со скриптами из `scripts/` и `templates/`.
3. Git-хук `format-and-test.sh` запускает форматирование и выборочные тесты, опираясь на кэш Gradle-проектов.
4. Пользователь управляет политиками доступа и пресетами через `.claude/settings.json` и `config/conventions.json`.

Детали настройки и расширения описаны в `docs/customization.md`.

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
/feature-tasks checkout-discounts
/commit "UC1: implement rule engine"
/test-changed
```

Результат:
- создаётся PRD/ADR/Tasklist;
- при правках срабатывает автоформат и выборочные тесты;
- `/commit` собирает сообщение в соответствии с активным режимом конвенций.

## Слэш-команды

| Команда | Назначение | Аргументы (пример) |
|---|---|---|
| `/branch-new` | Создать/переключить ветку по пресету | `feature STORE-123` / `feat orders` / `mixed STORE-123 feat pricing` |
| `/feature-new` | Создать PRD и стартовые артефакты | `checkout-discounts STORE-123` |
| `/feature-adr` | Сформировать ADR из PRD | `checkout-discounts` |
| `/feature-tasks` | Обновить `tasklist.md` | `checkout-discounts` |
| `/docs-generate` | Сгенерировать/обновить документацию | — |
| `/test-changed` | Прогнать тесты по затронутым Gradle-модулям | — |
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

Подробности и советы по тройблшутингу собраны в `docs/usage-demo.md` и `docs/customization.md`.

## Дополнительно
- Пошаговый пример использования и снимки до/после: `docs/usage-demo.md`.
- Руководство по настройке `.claude/settings.json`, `config/conventions.json`, хуков и CLI: `docs/customization.md`.
- Англоязычная версия README с правилами синхронизации: `README.en.md`.
- Демо-монорепо и скрипт применения: `examples/gradle-demo/`, `examples/apply-demo.sh`.

## Вклад и лицензия
- Перед отправкой изменений ознакомьтесь с `CONTRIBUTING.md`.
- Лицензия проекта — MIT (`LICENSE`).
- Проект не аффилирован с поставщиками IDE/инструментов; используйте на свой риск.
