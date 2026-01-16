# AIDD Claude Code Plugin - Language-agnostic Workflow Template

> Готовый плагин для Claude Code: слэш-команды, агенты, хуки и шаблоны для процесса idea → research → plan → review-spec → tasklist → implement → review → qa.

## Оглавление
- [Что это](#что-это)
- [Быстрый старт](#быстрый-старт)
- [Скрипты и проверки](#скрипты-и-проверки)
- [Слэш-команды](#слэш-команды)
- [Предпосылки](#предпосылки)
- [Диагностика путей](#диагностика-путей)
- [Документация](#документация)
- [Вклад](#вклад)
- [Лицензия](#лицензия)

## Что это
AIDD добавляет к проекту готовый процесс разработки с агентами и гейтами. Вы получаете структуру `aidd/`, набор слэш-команд и скриптов, а также единый способ вести PRD, планы и tasklist.

Ключевые возможности:
- Слэш-команды и агенты для цепочки idea → research → plan → review-spec → tasklist → implement → review → qa.
- Research обязателен перед планированием: `research-check` требует статус `reviewed`.
- Гейты PRD/Plan Review/QA и безопасные хуки (stage-aware).
- Автоформат и выборочные тесты на стадии `implement`.
- Единый формат ответов `AIDD:ANSWERS` + Q-идентификаторы в `AIDD:OPEN_QUESTIONS` (план ссылается на `PRD QN` без дублирования).
- Конвенции веток и коммитов через `aidd/config/conventions.json`.

## Быстрый старт

### 1. Подключите marketplace и установите плагин

```text
/plugin marketplace add GrinRus/ai_driven_dev
/plugin install feature-dev-aidd@aidd-local
```

### 2. Инициализируйте workspace

```text
/aidd-init
```

Для CI или ручного запуска:

```bash
PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli init
```

### 3. Запустите фичу в Claude Code

```text
/idea-new STORE-123 checkout-discounts
/researcher STORE-123
/plan-new STORE-123
/review-spec STORE-123
/tasks-new STORE-123
/implement STORE-123
/review STORE-123
/qa STORE-123
```

Примечания:
- `/idea-new` принимает `ticket` и опциональный `slug-hint`.
- После `/idea-new` ответьте аналитику и доведите PRD до `Status: READY` (проверьте `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli analyst-check --ticket STORE-123`).
- Ответы фиксируйте в `AIDD:ANSWERS` (формат `Answer N`) и синхронизируйте `AIDD:OPEN_QUESTIONS` как `Q1/Q2/...` — при наличии секции `AIDD:OPEN_QUESTIONS` `analyst-check` блокирует рассинхрон.
- В плане вместо дублирования вопросов используйте ссылки `PRD QN`.
- `/review-spec` выполняет review-plan и review-prd в одном шаге.

## Скрипты и проверки

| Команда | Назначение |
| --- | --- |
| `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli init` | Создать `./aidd` из шаблонов (без перезаписи) |
| `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli research --ticket <ticket>` | Сгенерировать research-контекст |
| `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli research-check --ticket <ticket>` | Проверить статус Research `reviewed` |
| `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli analyst-check --ticket <ticket>` | Проверить PRD `READY` и синхронизацию вопросов/ответов |
| `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli progress --source <stage> --ticket <ticket>` | Подтвердить прогресс tasklist |
| `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli qa --ticket <ticket> --report aidd/reports/qa/<ticket>.json --gate` | Сформировать QA отчёт и гейт |
| `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli tasklist-check --ticket <ticket>` | Проверить tasklist по канону |
| `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli tasks-derive --source <qa\|research\|review> --append --ticket <ticket>` | Добавить handoff-задачи |
| `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli status --ticket <ticket> [--refresh]` | Краткий статус тикета (stage/артефакты/события) |
| `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli index-sync --ticket <ticket>` | Обновить индекс тикета `aidd/docs/index/<ticket>.yaml` |
| `dev/repo_tools/ci-lint.sh` | CI/линтеры и юнит-тесты (repo-only) |
| `dev/repo_tools/smoke-workflow.sh` | E2E smoke для проверок в репозитории |

`dev/repo_tools/` — repo-only утилиты для CI/линтинга; в плагин не входят.

## Слэш-команды

| Команда | Назначение | Аргументы |
| --- | --- | --- |
| `/aidd-init` | Инициализировать workspace (`./aidd`) | `[--target <path>] [--force]` |
| `/idea-new` | Создать PRD draft и вопросы | `<TICKET> [slug-hint] [note...]` |
| `/researcher` | Собрать контекст и отчёт Researcher | `<TICKET> [note...] [--paths ... --keywords ... --note ...]` |
| `/plan-new` | План + валидация | `<TICKET> [note...]` |
| `/review-spec` | Review plan + PRD | `<TICKET> [note...]` |
| `/spec-interview` | Spec interview (опционально) | `<TICKET> [note...]` |
| `/tasks-new` | Сформировать tasklist | `<TICKET> [note...]` |
| `/implement` | Итеративная реализация | `<TICKET> [note...] [test=fast\|targeted\|full\|none] [tests=<filters>] [tasks=<task1,task2>]` |
| `/review` | Код-ревью и задачи | `<TICKET> [note...]` |
| `/qa` | Финальная QA-проверка | `<TICKET> [note...]` |
| `/status` | Статус тикета и артефакты | `[<TICKET>]` |

## Предпосылки
- `bash`, `git`, `python3`.
- Claude Code с доступом к plugin marketplace.
- Инструменты сборки/тестов вашего стека (по желанию).

Поддерживаются macOS/Linux. Для Windows используйте WSL или Git Bash.

## Диагностика путей
- Плагин живёт в корне репозитория (директории `commands/`, `agents/`, `hooks/`).
- Рабочие артефакты разворачиваются в `./aidd` после `/aidd-init`.
- Если команды или хуки не находят workspace, запустите `/aidd-init` или укажите `CLAUDE_PLUGIN_ROOT`.

## Документация
- Базовый workflow: `aidd/docs/sdlc-flow.md` (после init).
- Глубокий разбор и кастомизация: `dev/doc/workflow.md`, `dev/doc/customization.md`.
- Playbook агентов и QA: `dev/doc/agents-playbook.md`, `dev/doc/qa-playbook.md`.
- Английская версия: `README.en.md`.

## Вклад
Правила вкладов: `CONTRIBUTING.md`.

## Лицензия
MIT, подробнее: `LICENSE`.
