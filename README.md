# Claude Code Workflow - Language-agnostic Workflow Template

> Готовый шаблон и CLI для подключения Claude Code к любому репозиторию: слэш-команды, безопасные хуки, гейты по стадиям, выборочные проверки.

## Оглавление
- [Что это](#что-это)
- [Быстрый старт](#быстрый-старт)
- [CLI справка](#cli-справка)
- [Слэш-команды](#слэш-команды)
- [Предпосылки](#предпосылки)
- [Диагностика путей](#диагностика-путей)
- [Документация](#документация)
- [Вклад](#вклад)
- [Лицензия](#лицензия)

## Что это
Claude Code Workflow добавляет к проекту готовый процесс разработки с агентами и гейтами. Вы получаете структуру `aidd/`, набор команд и скриптов, а также единый способ вести PRD, планы и tasklist.

Ключевые возможности:
- Слэш-команды и агенты для цепочки idea -> research -> plan -> review-spec -> tasklist -> implement -> review -> qa.
- Research обязателен перед планированием: `research-check` требует статус `reviewed`.
- Гейты PRD/Plan Review/QA и безопасные хуки (stage-aware).
- Автоформат и выборочные тесты на стадии `implement`.
- Единый формат ответов `AIDD:ANSWERS` + Q-идентификаторы в `AIDD:OPEN_QUESTIONS` (план ссылается на `PRD QN` без дублирования).
- Конвенции веток и коммитов через `config/conventions.json`.

## Быстрый старт

### 1. Установите CLI

**Вариант A - uv (рекомендуется)**

```bash
uv tool install claude-workflow-cli --from git+https://github.com/GrinRus/ai_driven_dev.git
```

**Вариант B - pipx**

```bash
pipx install git+https://github.com/GrinRus/ai_driven_dev.git
```

**Вариант C - локально (bash-скрипт)**

```bash
PAYLOAD_ROOT="/path/to/ai_driven_dev/src/claude_workflow_cli/data/payload/aidd"
mkdir -p aidd
(cd aidd && bash "${PAYLOAD_ROOT}/init-claude-workflow.sh" --commit-mode ticket-prefix --enable-ci)
```

### 2. Инициализируйте workspace

```bash
claude-workflow init --target . --commit-mode ticket-prefix --enable-ci
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
- После `/idea-new` ответьте аналитику и доведите PRD до `Status: READY` (проверьте `claude-workflow analyst-check --ticket STORE-123`).
- Ответы фиксируйте в `AIDD:ANSWERS` (формат `Answer N`) и синхронизируйте `AIDD:OPEN_QUESTIONS` как `Q1/Q2/...` — при наличии секции `AIDD:OPEN_QUESTIONS` `analyst-check` блокирует рассинхрон.
- В плане вместо дублирования вопросов используйте ссылки `PRD QN`.
- `/review-spec` выполняет review-plan и review-prd в одном шаге.

## CLI справка

| Команда | Назначение |
| --- | --- |
| `claude-workflow init --target .` | Инициализация workspace и payload в `./aidd` |
| `claude-workflow sync` | Обновление `.claude/` (для `.claude-plugin/` добавьте `--include .claude-plugin`) |
| `claude-workflow upgrade --force` | Полная перезапись артефактов |
| `claude-workflow smoke` | E2E smoke-сценарий workflow |
| `claude-workflow research --ticket <ticket>` | Генерация research-контекста |
| `claude-workflow research-check --ticket <ticket>` | Проверка Research статуса `reviewed` |
| `claude-workflow analyst-check --ticket <ticket>` | Проверка PRD статуса `READY` и синхронизации `AIDD:OPEN_QUESTIONS`/`AIDD:ANSWERS` |
| `claude-workflow qa --ticket <ticket> --gate` | Запуск QA-отчёта и гейта |
| `claude-workflow progress --source <stage> --ticket <ticket>` | Подтверждение прогресса tasklist |

## Слэш-команды

| Команда | Назначение | Аргументы |
| --- | --- | --- |
| `/idea-new` | Создать PRD draft и вопросы | `<TICKET> [slug-hint] [note...]` |
| `/researcher` | Собрать контекст и отчёт Researcher | `<TICKET> [note...] [--paths ... --keywords ... --note ...]` |
| `/plan-new` | План + валидация | `<TICKET> [note...]` |
| `/review-spec` | Review plan + PRD | `<TICKET> [note...]` |
| `/tasks-new` | Сформировать tasklist | `<TICKET> [note...]` |
| `/implement` | Итеративная реализация | `<TICKET> [note...] [test=fast|targeted|full|none] [tests=<filters>] [tasks=<task1,task2>]` |
| `/review` | Код-ревью и задачи | `<TICKET> [note...]` |
| `/qa` | Финальная QA-проверка | `<TICKET> [note...]` |

## Предпосылки
- `bash`, `git`, `python3`.
- `uv` или `pipx` для установки CLI.
- Инструменты сборки/тестов вашего стека (по желанию).

Поддерживаются macOS/Linux. Для Windows используйте WSL или Git Bash.

## Диагностика путей
- Все артефакты находятся под `aidd/` (docs, reports, hooks).
- Если CLI не видит файлы, запускайте с `--target .` или из `aidd/`.
- Для ручной переадресации используйте `CLAUDE_PLUGIN_ROOT=./aidd`.

## Документация
- Базовый workflow: `aidd/docs/sdlc-flow.md`.
- Глубокий разбор и кастомизация: `doc/dev/workflow.md`, `doc/dev/customization.md`.
- Playbook агентов и QA: `doc/dev/agents-playbook.md`, `doc/dev/qa-playbook.md`.
- Английская версия: `README.en.md`.

## Вклад
Правила вкладов: `CONTRIBUTING.md`.

## Лицензия
MIT, подробнее: `LICENSE`.
