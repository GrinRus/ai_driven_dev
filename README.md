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
/feature-dev-aidd:aidd-init
```

Для CI или ручного запуска:

```bash
${CLAUDE_PLUGIN_ROOT}/tools/init.sh
```

### 3. Запустите фичу в Claude Code

```text
/feature-dev-aidd:idea-new STORE-123 checkout-discounts
/feature-dev-aidd:researcher STORE-123
/feature-dev-aidd:plan-new STORE-123
/feature-dev-aidd:review-spec STORE-123
/feature-dev-aidd:tasks-new STORE-123
/feature-dev-aidd:implement STORE-123
/feature-dev-aidd:review STORE-123
/feature-dev-aidd:qa STORE-123
```

Примечания:
- `/feature-dev-aidd:idea-new` принимает `ticket` и опциональный `slug-hint`.
- После `/feature-dev-aidd:idea-new` ответьте аналитику и доведите PRD до `Status: READY` (проверьте `${CLAUDE_PLUGIN_ROOT}/tools/analyst-check.sh --ticket STORE-123`).
- Ответы фиксируйте в `AIDD:ANSWERS` (формат `Answer N`) и синхронизируйте `AIDD:OPEN_QUESTIONS` как `Q1/Q2/...` — при наличии секции `AIDD:OPEN_QUESTIONS` `analyst-check` блокирует рассинхрон.
- В плане вместо дублирования вопросов используйте ссылки `PRD QN`.
- `/feature-dev-aidd:review-spec` выполняет review-plan и review-prd в одном шаге.

## Скрипты и проверки

| Команда | Назначение |
| --- | --- |
| `${CLAUDE_PLUGIN_ROOT}/tools/init.sh` | Создать `./aidd` из шаблонов (без перезаписи) |
| `${CLAUDE_PLUGIN_ROOT}/tools/doctor.sh [--target <path>]` | Диагностика окружения, путей и наличия `aidd/` |
| `${CLAUDE_PLUGIN_ROOT}/tools/research.sh --ticket <ticket>` | Сгенерировать research-контекст |
| `${CLAUDE_PLUGIN_ROOT}/tools/research-check.sh --ticket <ticket>` | Проверить статус Research `reviewed` |
| `${CLAUDE_PLUGIN_ROOT}/tools/analyst-check.sh --ticket <ticket>` | Проверить PRD `READY` и синхронизацию вопросов/ответов |
| `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source <stage> --ticket <ticket>` | Подтвердить прогресс tasklist |
| `${CLAUDE_PLUGIN_ROOT}/tools/qa.sh --ticket <ticket> --report aidd/reports/qa/<ticket>.json --gate` | Сформировать QA отчёт и гейт |
| `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh --ticket <ticket>` | Проверить tasklist по канону |
| `${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh --source <qa\|research\|review> --append --ticket <ticket>` | Добавить handoff-задачи |
| `${CLAUDE_PLUGIN_ROOT}/tools/status.sh --ticket <ticket> [--refresh]` | Краткий статус тикета (stage/артефакты/события) |
| `${CLAUDE_PLUGIN_ROOT}/tools/index-sync.sh --ticket <ticket>` | Обновить индекс тикета `aidd/docs/index/<ticket>.yaml` |
| `dev/repo_tools/ci-lint.sh` | CI/линтеры и юнит-тесты (repo-only) |
| `dev/repo_tools/smoke-workflow.sh` | E2E smoke для проверок в репозитории |

`dev/repo_tools/` — repo-only утилиты для CI/линтинга; в плагин не входят.

## Слэш-команды

| Команда | Назначение | Аргументы |
| --- | --- | --- |
| `/feature-dev-aidd:aidd-init` | Инициализировать workspace (`./aidd`) | `[--target <path>] [--force]` |
| `/feature-dev-aidd:idea-new` | Создать PRD draft и вопросы | `<TICKET> [slug-hint] [note...]` |
| `/feature-dev-aidd:researcher` | Собрать контекст и отчёт Researcher | `<TICKET> [note...] [--paths ... --keywords ... --note ...]` |
| `/feature-dev-aidd:plan-new` | План + валидация | `<TICKET> [note...]` |
| `/feature-dev-aidd:review-spec` | Review plan + PRD | `<TICKET> [note...]` |
| `/feature-dev-aidd:spec-interview` | Spec interview (опционально) | `<TICKET> [note...]` |
| `/feature-dev-aidd:tasks-new` | Сформировать tasklist | `<TICKET> [note...]` |
| `/feature-dev-aidd:implement` | Итеративная реализация | `<TICKET> [note...] [test=fast\|targeted\|full\|none] [tests=<filters>] [tasks=<task1,task2>]` |
| `/feature-dev-aidd:review` | Код-ревью и задачи | `<TICKET> [note...]` |
| `/feature-dev-aidd:qa` | Финальная QA-проверка | `<TICKET> [note...]` |
| `/feature-dev-aidd:status` | Статус тикета и артефакты | `[<TICKET>]` |

## Предпосылки
- `bash`, `git`, `python3`.
- Claude Code с доступом к plugin marketplace.
- Инструменты сборки/тестов вашего стека (по желанию).

Поддерживаются macOS/Linux. Для Windows используйте WSL или Git Bash.

## Диагностика путей
- Плагин живёт в корне репозитория (директории `commands/`, `agents/`, `hooks/`).
- Рабочие артефакты разворачиваются в `./aidd` после `/feature-dev-aidd:aidd-init`.
- Если команды или хуки не находят workspace, запустите `/feature-dev-aidd:aidd-init` или укажите `CLAUDE_PLUGIN_ROOT`.
- Для быстрой проверки окружения используйте `${CLAUDE_PLUGIN_ROOT}/tools/doctor.sh --target .`.

## Документация
- Базовый workflow: `aidd/docs/sdlc-flow.md` (после init).
- Глубокий разбор и кастомизация: `dev/doc/workflow.md`, `dev/doc/customization.md`.
- Playbook агентов и QA: `dev/doc/agents-playbook.md`, `dev/doc/qa-playbook.md`.
- Английская версия: `README.en.md`.

## Вклад
Правила вкладов: `CONTRIBUTING.md`.

## Лицензия
MIT, подробнее: `LICENSE`.
