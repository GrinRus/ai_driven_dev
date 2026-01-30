# AIDD Claude Code Plugin - Language-agnostic Workflow Template

> Готовый плагин для Claude Code: слэш-команды, агенты, хуки и шаблоны для процесса idea → research → plan → review-spec → spec-interview (опционально) → tasklist → implement → review → qa.

## Оглавление
- [Что это](#что-это)
- [Быстрый старт](#быстрый-старт)
- [Скрипты и проверки](#скрипты-и-проверки)
- [Слэш-команды](#слэш-команды)
- [Предпосылки](#предпосылки)
- [Диагностика путей](#диагностика-путей)
- [Документация](#документация)
- [Примеры](#примеры)
- [Вклад](#вклад)
- [Лицензия](#лицензия)

## Что это
AIDD — это AI-Driven Development: LLM работает не как «один большой мозг», а как команда ролей внутри привычного SDLC. Плагин для Claude Code помогает уйти от вайб-коддинга: фиксирует артефакты (PRD/plan/tasklist/отчёты), проводит через quality‑гейты и добавляет агентов, слэш‑команды, хуки и структуру `aidd/`.

Ключевые возможности:
- Слэш-команды и агенты для цепочки idea → research → plan → review-spec → spec-interview (опционально) → tasklist → implement → review → qa.
- Research обязателен перед планированием: `research-check` требует статус `reviewed`.
- Гейты PRD/Plan Review/QA и безопасные хуки (stage-aware).
- Автоформат и выборочные тесты на стадии `implement`.
- Loop mode implement↔review: loop pack/review pack, diff boundary guard, loop-step/loop-run.
- Architecture Profile как канон архитектурных ограничений и процессов тестов/формата/запуска (если они описаны в проекте).
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

Если хотите сразу заполнить `.claude/settings.json` дефолтами `automation.tests`, используйте:

```text
/feature-dev-aidd:aidd-init --detect-build-tools
```

Для автозаполнения `stack_hint` в Architecture Profile:

```text
/feature-dev-aidd:aidd-init --detect-stack
```

### 3. Запустите фичу в Claude Code

```text
/feature-dev-aidd:idea-new STORE-123 checkout-discounts
/feature-dev-aidd:researcher STORE-123
/feature-dev-aidd:plan-new STORE-123
/feature-dev-aidd:review-spec STORE-123
/feature-dev-aidd:spec-interview STORE-123
/feature-dev-aidd:tasks-new STORE-123
/feature-dev-aidd:implement STORE-123
/feature-dev-aidd:review STORE-123
/feature-dev-aidd:qa STORE-123
```

Примечания:
- Вопросы могут появляться после `/feature-dev-aidd:idea-new`, `/feature-dev-aidd:review-spec` и `/feature-dev-aidd:spec-interview` (если запускаете).
- Ответы давайте в `AIDD:ANSWERS` (формат `Answer N`), а фиксацию/синхронизацию должен выполнить тот же агент/команда, которые задали вопросы.

### Миграция
- `/feature-dev-aidd:aidd-init` без `--force` добавляет новые артефакты и не перезаписывает существующие.
- Для обновления шаблонов используйте `--force` или перенесите изменения вручную.
- Root `AGENTS.md` — dev‑гайд репозитория; пользовательский канон процесса — `aidd/AGENTS.md` (копируется из `templates/aidd/AGENTS.md`).

## Скрипты и проверки

| Команда | Назначение |
| --- | --- |
| `${CLAUDE_PLUGIN_ROOT}/tools/init.sh` | Создать `./aidd` из шаблонов (без перезаписи) |
| `${CLAUDE_PLUGIN_ROOT}/tools/doctor.sh` | Диагностика окружения, путей и наличия `aidd/` |
| `${CLAUDE_PLUGIN_ROOT}/tools/research.sh --ticket <ticket>` | Сгенерировать research-контекст |
| `${CLAUDE_PLUGIN_ROOT}/tools/research-check.sh --ticket <ticket>` | Проверить статус Research `reviewed` |
| `${CLAUDE_PLUGIN_ROOT}/tools/analyst-check.sh --ticket <ticket>` | Проверить PRD `READY` и синхронизацию вопросов/ответов |
| `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source <stage> --ticket <ticket>` | Подтвердить прогресс tasklist |
| `${CLAUDE_PLUGIN_ROOT}/tools/loop-pack.sh --ticket <ticket> --stage implement\|review` | Сформировать loop pack для текущего work_item |
| `${CLAUDE_PLUGIN_ROOT}/tools/review-pack.sh --ticket <ticket>` | Сформировать review pack (тонкий feedback) |
| `${CLAUDE_PLUGIN_ROOT}/tools/diff-boundary-check.sh --ticket <ticket>` | Проверить diff против allowed_paths (loop-pack) |
| `${CLAUDE_PLUGIN_ROOT}/tools/loop-step.sh --ticket <ticket>` | Один шаг loop (implement↔review) |
| `${CLAUDE_PLUGIN_ROOT}/tools/loop-run.sh --ticket <ticket> --max-iterations 5` | Авто-loop до SHIP |
| `${CLAUDE_PLUGIN_ROOT}/tools/qa.sh --ticket <ticket> --report aidd/reports/qa/<ticket>.json --gate` | Сформировать QA отчёт и гейт |
| `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh --ticket <ticket>` | Проверить tasklist по канону |
| `${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh --source <qa\|research\|review> --append --ticket <ticket>` | Добавить handoff-задачи |
| `${CLAUDE_PLUGIN_ROOT}/tools/status.sh --ticket <ticket> [--refresh]` | Краткий статус тикета (stage/артефакты/события) |
| `${CLAUDE_PLUGIN_ROOT}/tools/index-sync.sh --ticket <ticket>` | Обновить индекс тикета `aidd/docs/index/<ticket>.json` |
| `tests/repo_tools/ci-lint.sh` | CI/линтеры и юнит-тесты (repo-only) |
| `tests/repo_tools/smoke-workflow.sh` | E2E smoke для проверок в репозитории |

`tests/repo_tools/` — repo-only утилиты для CI/линтинга; в плагин не входят.

## Слэш-команды

| Команда | Назначение | Аргументы |
| --- | --- | --- |
| `/feature-dev-aidd:aidd-init` | Инициализировать workspace (`./aidd`) | `[--force] [--detect-build-tools] [--detect-stack]` |
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

## Research RLM

RLM evidence используется как основной источник интеграций/рисков/связей (pack-first + slice on demand).
Legacy `ast_grep` evidence deprecated и disabled by default.

Troubleshooting пустого контекста:
- Уточните `--paths`/`--keywords` (указывайте реальный код, не только `aidd/`).
- Проверьте `--paths-relative workspace`, если код лежит вне `aidd/`.
- Если `rlm_status=pending`, выполните agent‑flow по worklist и пересоберите RLM pack.

RLM artifacts (pack-first):
- Pack summary: `aidd/reports/research/<ticket>-rlm.pack.json`.
- Slice-инструмент: `${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh --ticket <ticket> --query "<token>" [--paths path1,path2] [--lang kt,java]`.
- Бюджет `*-context.pack.json`: `config/conventions.json` → `reports.research_pack_budget` (по умолчанию `max_chars=2000`, `max_lines=120`).

## Loop mode (implement↔review)

Loop = 1 work_item → implement → review → (revise)* → ship.

Ключевые артефакты:
- `aidd/reports/loops/<ticket>/<work_item_key>.loop.pack.md` — тонкий контекст итерации.
- `aidd/reports/loops/<ticket>/review.latest.pack.md` — краткий feedback с verdict.

Команды:
- Manual: `/feature-dev-aidd:implement <ticket>` → `/feature-dev-aidd:review <ticket>`.
- Bash loop: `${CLAUDE_PLUGIN_ROOT}/tools/loop-step.sh --ticket <ticket>` (fresh sessions).
- One-shot: `${CLAUDE_PLUGIN_ROOT}/tools/loop-run.sh --ticket <ticket> --max-iterations 5`.
- Scope guard: `${CLAUDE_PLUGIN_ROOT}/tools/diff-boundary-check.sh --ticket <ticket>`.

Примечание:
- Ralph plugin использует stop-hook в той же сессии (completion promise). AIDD loop-mode — fresh sessions.
- Для max-iterations используйте формат с пробелом: `--max-iterations 5` (без `=`).

Правила:
- Loop pack first, без больших вставок логов/диффов (ссылки на `aidd/reports/**`).
- Review не расширяет scope: новое → `AIDD:OUT_OF_SCOPE_BACKLOG` или новый work_item.
- Allowed paths берутся из `Expected paths` итерации (`AIDD:ITERATIONS_FULL`).
- Loop-mode тесты: implement не запускает тесты по умолчанию; нужен `AIDD_LOOP_TESTS=1` или `AIDD_TEST_FORCE=1`. Review тесты не запускает.

## Предпосылки
- `bash`, `git`, `python3`.
- Claude Code с доступом к plugin marketplace.
- Инструменты сборки/тестов вашего стека (по желанию).
- MCP интеграции опциональны: `.mcp.json` не входит в плагин по умолчанию.

Поддерживаются macOS/Linux. Для Windows используйте WSL или Git Bash.

## Диагностика путей
- Плагин живёт в корне репозитория (директории `commands/`, `agents/`, `hooks/`).
- Рабочие артефакты разворачиваются в `./aidd` после `/feature-dev-aidd:aidd-init`.
- Если команды или хуки не находят workspace, запустите `/feature-dev-aidd:aidd-init` или укажите `CLAUDE_PLUGIN_ROOT`.
- Для быстрой проверки окружения используйте `${CLAUDE_PLUGIN_ROOT}/tools/doctor.sh`.

## Документация
- Базовый workflow: `aidd/docs/sdlc-flow.md` (после init).
- Architecture Profile: `aidd/docs/architecture/profile.md`.
- Пользовательский гайд: `aidd/AGENTS.md`; dev‑гайд репозитория: `AGENTS.md`.
- Английская версия: `README.en.md`.

## Примеры
Демо‑проекты и вспомогательные скрипты не поставляются — репозиторий остаётся language‑agnostic. При необходимости держите демо‑проекты вне плагина и описывайте их в документации вашего workspace.

## Dev-only проверки
- Репозиторные проверки (maintainer only): `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/smoke-workflow.sh`.

## Вклад
Правила вкладов: `CONTRIBUTING.md`.

## Лицензия
MIT, подробнее: `LICENSE`.
