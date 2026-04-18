# AIDD Claude Code Plugin

> Минимальный artifact-driven workflow для Claude Code: idea -> research -> plan -> review-spec -> tasklist -> implement -> review -> qa.

## Кратко
AIDD добавляет компактный staged-workflow, слэш-команды и базовые guardrails вокруг артефактов `prd`, `plan`, `tasklist`, `qa`.

## Требования
- Claude Code с поддержкой plugin marketplace команд.
- Minimum tested version: Claude Code `1.0.0`.
- `python3`, `git`, `rg`.

## Установка
```text
/plugin marketplace add GrinRus/ai_driven_dev
/plugin install feature-dev-aidd@aidd-local
```

Self-hosted канал обновляется только через immutable tag refs `vX.Y.Z`.

## Быстрый старт
```text
/feature-dev-aidd:aidd-init
/feature-dev-aidd:idea-new TICKET-123 "Короткое описание"
/feature-dev-aidd:researcher TICKET-123
/feature-dev-aidd:plan-new TICKET-123
/feature-dev-aidd:review-spec TICKET-123
/feature-dev-aidd:tasks-new TICKET-123
/feature-dev-aidd:implement TICKET-123
/feature-dev-aidd:review TICKET-123
/feature-dev-aidd:qa TICKET-123
```

## Основные команды
- `/feature-dev-aidd:aidd-init` разворачивает `aidd/` в workspace.
- `/feature-dev-aidd:idea-new`, `researcher`, `plan-new`, `review-spec`, `tasks-new` строят цепочку артефактов.
- `/feature-dev-aidd:implement`, `review`, `qa` ведут bounded delivery loop.
- `/feature-dev-aidd:status [ticket]` показывает текущее состояние фичи.

Loop mode entrypoints:
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_step.py --ticket TICKET-123`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_run.py --ticket TICKET-123 --max-iterations 5`

## Обновление
```text
/plugin update feature-dev-aidd@aidd-local
```
После обновления перезапустите сессию Claude Code.

## Диагностика
- После обновления не видны команды: снова выполните `/plugin update feature-dev-aidd@aidd-local` и перезапустите Claude Code.
- Ошибка `ModuleNotFoundError: No module named 'aidd_runtime'`: переустановите плагин и перезапустите сессию.
- Workspace не инициализирован: выполните `/feature-dev-aidd:aidd-init`, затем `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-observability/runtime/doctor.py`.

## Документация
### Public docs
- `README.md` и `README.en.md` — установка, запуск, обновление.
- `CHANGELOG.md` — пользовательские release notes.
- `SECURITY.md` и `SUPPORT.md` — security disclosure и support policy.
- `CONTRIBUTING.md` и `CODE_OF_CONDUCT.md` — правила вкладов и поведения.

## Вклад
Процесс вкладов: `CONTRIBUTING.md`.

## Лицензия
MIT, подробности: `LICENSE`.
