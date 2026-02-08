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
- Skill-first промпты: канон выполнения/контракт вывода живут в `skills/aidd-core` и `skills/aidd-loop` (EN); stage entrypoints определяются skill-файлами.
- Research обязателен перед планированием: `research-check` требует статус `reviewed`.
- Гейты PRD/Plan Review/QA и безопасные хуки (stage-aware).
- Rolling context pack (pack-first): `aidd/reports/context/<ticket>.pack.md`.
- Hooks mode: по умолчанию `AIDD_HOOKS_MODE=fast`, строгий режим — `AIDD_HOOKS_MODE=strict`.
- Автоформат + тест‑политика по стадиям: `implement` — без тестов, `review` — targeted, `qa` — full.
- Loop mode implement↔review: loop pack/review pack, diff boundary guard, loop-step/loop-run.
- Единый формат ответов `AIDD:ANSWERS` + Q-идентификаторы в `AIDD:OPEN_QUESTIONS` (план ссылается на `PRD QN` без дублирования).
- Конвенции веток и коммитов через `aidd/config/conventions.json`.

## SKILL-first runtime path policy
- Stage-specific entrypoints: canonical путь `skills/<stage>/scripts/*`.
- Shared entrypoints: целевой canonical путь `skills/aidd-core/scripts/*` (поэтапная миграция).
- `tools/*` в migration window используются как orchestrator/deferred-core API или compatibility shims.
- Deferred-core API (wave-1 freeze): `tools/init.sh`, `tools/research.sh`, `tools/tasks-derive.sh`, `tools/actions-apply.sh`, `tools/context-expand.sh`.
- Любой shim обязан печатать deprecation warning и `exec`-делегировать на canonical path с сохранением exit code.
- Stage lexicon: public stage `review-spec` работает как umbrella для internal `review-plan` и `review-prd`.

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

`/feature-dev-aidd:aidd-init` создаёт `./aidd` и `.claude/settings.json` с дефолтами `automation.tests`. Для обновления/детекта под стек используйте:

```text
/feature-dev-aidd:aidd-init --detect-build-tools
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

### Обновление workspace
- `/feature-dev-aidd:aidd-init` без `--force` добавляет новые артефакты и не перезаписывает существующие.
- Для обновления шаблонов используйте `--force` или перенесите изменения вручную.
- Root `AGENTS.md` — dev‑гайд репозитория; пользовательский канон процесса — `aidd/AGENTS.md` (копируется из `templates/aidd/AGENTS.md`).

## Скрипты и проверки

| Команда | Назначение |
| --- | --- |
| `${CLAUDE_PLUGIN_ROOT}/tools/init.sh` | Создать `./aidd` из шаблонов (без перезаписи) |
| `${CLAUDE_PLUGIN_ROOT}/tools/doctor.sh` | Диагностика окружения, путей и наличия `aidd/` |
| `${CLAUDE_PLUGIN_ROOT}/skills/researcher/scripts/research.sh --ticket <ticket>` | Сгенерировать research-контекст (legacy shim: `${CLAUDE_PLUGIN_ROOT}/tools/research.sh`) |
| `${CLAUDE_PLUGIN_ROOT}/skills/plan-new/scripts/research-check.sh --ticket <ticket>` | Проверить статус Research `reviewed` (legacy shim: `${CLAUDE_PLUGIN_ROOT}/tools/research-check.sh`) |
| `${CLAUDE_PLUGIN_ROOT}/skills/idea-new/scripts/analyst-check.sh --ticket <ticket>` | Проверить PRD `READY` и синхронизацию вопросов/ответов (legacy shim: `${CLAUDE_PLUGIN_ROOT}/tools/analyst-check.sh`) |
| `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source <stage> --ticket <ticket>` | Подтвердить прогресс tasklist |
| `${CLAUDE_PLUGIN_ROOT}/tools/loop-pack.sh --ticket <ticket> --stage implement\|review` | Сформировать loop pack для текущего work_item |
| `${CLAUDE_PLUGIN_ROOT}/skills/review/scripts/review-report.sh --ticket <ticket> --findings-file <path> --status warn` | Сформировать review report |
| `${CLAUDE_PLUGIN_ROOT}/skills/review/scripts/review-pack.sh --ticket <ticket>` | Сформировать review pack (тонкий feedback) |
| `${CLAUDE_PLUGIN_ROOT}/skills/review/scripts/reviewer-tests.sh --ticket <ticket> --status required\|optional` | Обновить reviewer marker для тестовой политики |
| `${CLAUDE_PLUGIN_ROOT}/tools/diff-boundary-check.sh --ticket <ticket>` | Проверить diff против allowed_paths (loop-pack) |
| `${CLAUDE_PLUGIN_ROOT}/tools/loop-step.sh --ticket <ticket>` | Один шаг loop (implement↔review) |
| `${CLAUDE_PLUGIN_ROOT}/tools/loop-run.sh --ticket <ticket> --max-iterations 5` | Авто-loop до завершения всех открытых итераций |
| `${CLAUDE_PLUGIN_ROOT}/skills/qa/scripts/qa.sh --ticket <ticket> --report aidd/reports/qa/<ticket>.json --gate` | Сформировать QA отчёт и гейт (legacy shim: `${CLAUDE_PLUGIN_ROOT}/tools/qa.sh`) |
| `${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh --ticket <ticket>` | Проверить tasklist по канону |
| `${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh --source <qa\|research\|review> --append --ticket <ticket>` | Добавить handoff-задачи |
| `${CLAUDE_PLUGIN_ROOT}/skills/status/scripts/status.sh --ticket <ticket> [--refresh]` | Краткий статус тикета (legacy shim: `${CLAUDE_PLUGIN_ROOT}/tools/status.sh`) |
| `${CLAUDE_PLUGIN_ROOT}/tools/status-summary.sh --ticket <ticket> --stage <implement\|review\|qa>` | Финальный статус из stage_result (single source) |
| `${CLAUDE_PLUGIN_ROOT}/skills/status/scripts/index-sync.sh --ticket <ticket>` | Обновить индекс тикета (legacy shim: `${CLAUDE_PLUGIN_ROOT}/tools/index-sync.sh`) |
| `tests/repo_tools/ci-lint.sh` | CI/линтеры и юнит-тесты (repo-only) |
| `tests/repo_tools/smoke-workflow.sh` | E2E smoke для проверок в репозитории |

`tests/repo_tools/` — repo-only утилиты для CI/линтинга; в плагин не входят.

`tools/review-report.sh`, `tools/review-pack.sh`, `tools/reviewer-tests.sh` остаются как deprecated shim (compatibility-only) и выводят предупреждение.

## Слэш-команды

| Команда | Назначение | Аргументы |
| --- | --- | --- |
| `/feature-dev-aidd:aidd-init` | Инициализировать workspace (`./aidd`) | `[--force] [--detect-build-tools]` |
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
Если после SHIP есть открытые итерации в `AIDD:NEXT_3`/`AIDD:ITERATIONS_FULL`, loop-run выбирает следующий work_item, обновляет `aidd/docs/.active.json` (work_item/stage) и продолжает implement.

Ключевые артефакты:
- `aidd/reports/loops/<ticket>/<scope_key>.loop.pack.md` — тонкий контекст итерации.
- `aidd/reports/loops/<ticket>/<scope_key>/review.latest.pack.md` — краткий feedback с verdict.

Команды:
- Manual: `/feature-dev-aidd:implement <ticket>` → `/feature-dev-aidd:review <ticket>`.
- Bash loop: `${CLAUDE_PLUGIN_ROOT}/tools/loop-step.sh --ticket <ticket>` (fresh sessions).
- One-shot: `${CLAUDE_PLUGIN_ROOT}/tools/loop-run.sh --ticket <ticket> --max-iterations 5`.
- Scope guard: `${CLAUDE_PLUGIN_ROOT}/tools/diff-boundary-check.sh --ticket <ticket>`.
- Stream (optional): `${CLAUDE_PLUGIN_ROOT}/tools/loop-step.sh --ticket <ticket> --stream=text|tools|raw`,
   `${CLAUDE_PLUGIN_ROOT}/tools/loop-run.sh --ticket <ticket> --stream`.

Пример запуска из корня проекта:
```bash
CLAUDE_PLUGIN_ROOT="/path/to/ai_driven_dev" "$CLAUDE_PLUGIN_ROOT/tools/loop-run.sh" --ticket ABC-123 --max-iterations 5
```

Примечание:
- Ralph plugin использует stop-hook в той же сессии (completion promise). AIDD loop-mode — fresh sessions.
- Для max-iterations используйте формат с пробелом: `--max-iterations 5` (без `=`).
- Если `CLAUDE_PLUGIN_ROOT`/`AIDD_PLUGIN_DIR` не задан, loop-скрипты пытаются auto-detect по пути скрипта и печатают WARN; при недоступности авто‑детекта — BLOCKED.
- Stream логи: `aidd/reports/loops/<ticket>/cli.loop-*.stream.log` (human) и `aidd/reports/loops/<ticket>/cli.loop-*.stream.jsonl` (raw).
- Loop run log: `aidd/reports/loops/<ticket>/loop.run.log`.
- Настройки cadence/tests хранятся в `.claude/settings.json` в корне workspace (без `aidd/.claude`).

Правила:
- Loop pack first, без больших вставок логов/диффов (ссылки на `aidd/reports/**`).
- Review не расширяет scope: новое → `AIDD:OUT_OF_SCOPE_BACKLOG` или новый work_item.
- Review pack обязателен; при наличии review report + loop pack допускается авто‑пересборка.
- Финальный Status в командах implement/review/qa должен совпадать со `stage_result`.
- Allowed paths берутся из `Expected paths` итерации (`AIDD:ITERATIONS_FULL`).
- Loop-mode тесты следуют stage policy: `implement` — без тестов, `review` — targeted, `qa` — full.
- Tests evidence: `tests_log` со `status=skipped` + `reason_code` считается evidence при `tests_required=soft` (для `hard` → BLOCKED).

## Предпосылки
- `bash`, `git`, `python3`.
- Claude Code с доступом к plugin marketplace.
- Инструменты сборки/тестов вашего стека (по желанию).
- MCP интеграции опциональны: `.mcp.json` не входит в плагин по умолчанию.

Поддерживаются macOS/Linux. Для Windows используйте WSL или Git Bash.

## Диагностика путей
- Плагин живёт в корне репозитория (директории `agents/`, `skills/`, `hooks/`, `tools/`).
- Рабочие артефакты разворачиваются в `./aidd` после `/feature-dev-aidd:aidd-init`.
- Если команды или хуки не находят workspace, запустите `/feature-dev-aidd:aidd-init` или укажите `CLAUDE_PLUGIN_ROOT`.
- Для быстрой проверки окружения используйте `${CLAUDE_PLUGIN_ROOT}/tools/doctor.sh`.

## Документация
- Канон ответа и pack-first: `aidd/docs/prompting/conventions.md`.
- Пользовательский гайд (runtime): `aidd/AGENTS.md`; dev‑гайд репозитория: `AGENTS.md`.
- Skill-first канон: `skills/aidd-core` и `skills/aidd-loop` (EN).
- Английская версия: `README.en.md`.

## Примеры
Демо‑проекты и вспомогательные скрипты не поставляются — репозиторий остаётся language‑agnostic. При необходимости держите демо‑проекты вне плагина и описывайте их в документации вашего workspace.

## Dev-only проверки
- Репозиторные проверки (maintainer only): `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/smoke-workflow.sh`.

## Вклад
Правила вкладов: `CONTRIBUTING.md`.

## Лицензия
MIT, подробнее: `LICENSE`.
