# AIDD Claude Code Plugin - Language-agnostic Workflow Template

> Готовый плагин для Claude Code: слэш-команды, агенты, хуки и шаблоны для процесса idea -> research -> plan -> review-spec -> spec-interview (optional) -> tasklist -> implement -> review -> qa.

## Оглавление
- [Что это](#что-это)
- [Быстрый старт](#быстрый-старт)
- [Скрипты и проверки](#скрипты-и-проверки)
- [Слэш-команды](#слэш-команды)
- [Документация](#документация)
- [Предпосылки](#предпосылки)
- [Вклад](#вклад)
- [Лицензия](#лицензия)

## Что это
AIDD (AI-Driven Development) организует работу LLM как workflow с артефактами и гейтами, а не как разовые ad-hoc ответы.

Коротко о модели:
- артефакты `aidd/docs/**` и `aidd/reports/**` являются рабочим контуром проекта;
- публичный stage-flow: `idea -> research -> plan -> review-spec -> tasklist -> implement -> review -> qa`;
- canonical runtime entrypoints: `skills/*/runtime/*.py`;
- hook entrypoints переведены на `hooks/*.py`;
- repo проверяется guard'ами и smoke/e2e сценариями.

Breaking-изменения путей и entrypoints см. в runbook:
- [docs/runbooks/prod-like-breaking-migration.md](docs/runbooks/prod-like-breaking-migration.md)

## Быстрый старт

### 1) Установите плагин
```text
/plugin marketplace add GrinRus/ai_driven_dev
/plugin install feature-dev-aidd@aidd-local
```

### 2) Инициализируйте workspace
```text
/feature-dev-aidd:aidd-init
```

### 3) Пройдите feature-flow
```text
/feature-dev-aidd:idea-new STORE-123 "Checkout: скидки, купоны, защита от double-charge"
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
- `spec-interview` опционален.
- `/feature-dev-aidd:aidd-init` без `--force` не перезаписывает существующие файлы.
- Пользовательский runtime-гайд появляется в workspace как `aidd/AGENTS.md`.

## Скрипты и проверки

| Команда | Назначение |
| --- | --- |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-init/runtime/init.py` | Инициализация `./aidd` из шаблонов |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-observability/runtime/doctor.py` | Диагностика окружения и путей |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/researcher/runtime/research.py --ticket <ticket>` | Сбор RLM research-артефактов |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/progress_cli.py --source <stage> --ticket <ticket>` | Проверка прогресса tasklist |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_step.py --ticket <ticket>` | Один шаг loop (fresh session) |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_run.py --ticket <ticket> --max-iterations 5` | Авто-loop implement/review |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/qa/runtime/qa.py --ticket <ticket> --gate` | QA-отчёт + gate |
| `tests/repo_tools/ci-lint.sh` | Линтеры + unit/integration тесты репозитория |
| `tests/repo_tools/smoke-workflow.sh` | E2E smoke workflow репозитория |
| `python3 tests/repo_tools/dist_manifest_check.py --root .` | Проверка состава дистрибутива |

Политики проверок, guard'ов и ownership-карта: [AGENTS.md](AGENTS.md).

## Слэш-команды

| Команда | Назначение | Аргументы |
| --- | --- | --- |
| `/feature-dev-aidd:aidd-init` | Инициализация workspace | `[--force] [--detect-build-tools]` |
| `/feature-dev-aidd:idea-new` | PRD draft + вопросы | `<TICKET> [note...]` |
| `/feature-dev-aidd:researcher` | Research stage | `<TICKET> [note...] [--paths ... --keywords ...]` |
| `/feature-dev-aidd:plan-new` | План и проверки | `<TICKET> [note...]` |
| `/feature-dev-aidd:review-spec` | Review plan + PRD | `<TICKET> [note...]` |
| `/feature-dev-aidd:spec-interview` | Дополнительный сбор уточнений | `<TICKET> [note...]` |
| `/feature-dev-aidd:tasks-new` | Формирование tasklist | `<TICKET> [note...]` |
| `/feature-dev-aidd:implement` | Реализация по итерациям | `<TICKET> [note...]` |
| `/feature-dev-aidd:review` | Code review + handoff-задачи | `<TICKET> [note...]` |
| `/feature-dev-aidd:qa` | Финальная QA-проверка | `<TICKET> [note...]` |
| `/feature-dev-aidd:status` | Сводный статус тикета | `[<TICKET>]` |

## Документация
- [AGENTS.md](AGENTS.md) - dev-policy и source-of-truth карта репозитория.
- [README.en.md](README.en.md) - английская версия этого README.
- [docs/runbooks/prod-like-breaking-migration.md](docs/runbooks/prod-like-breaking-migration.md) - migration runbook по breaking path changes.
- [docs/agent-skill-best-practices.md](docs/agent-skill-best-practices.md) - канон по авторингу skills.
- [docs/skill-language.md](docs/skill-language.md) - language/lint политика для prompts и skills.
- [docs/memory-v2-rfc.md](docs/memory-v2-rfc.md) - draft RFC по Memory v2.

## Предпосылки
- `python3`, `rg`, `git`.
- Claude Code с доступом к plugin marketplace.
- Для maintainer-проверок дополнительно: `shellcheck`, `markdownlint`, `yamllint`.

## Вклад
Процесс контрибуций: [CONTRIBUTING.md](CONTRIBUTING.md).

## Лицензия
MIT, см. [LICENSE](LICENSE).
