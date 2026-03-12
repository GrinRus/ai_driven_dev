# AIDD Claude Code Plugin

> Минимальный шаблон AI-driven workflow для Claude Code: idea -> research -> plan -> review-spec -> tasklist -> implement -> review -> qa.

## Что это
AIDD добавляет в Claude Code готовый workflow, слэш-команды и базовые проверки для разработки через артефакты (`prd`, `plan`, `tasklist`, `qa`).

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

## Слэш-команды

| Команда | Когда запускать |
| --- | --- |
| `/feature-dev-aidd:aidd-init` | Один раз на workspace или после удаления `aidd/`. |
| `/feature-dev-aidd:idea-new <ticket> "<note>"` | Старт фичи и создание PRD-драфта. |
| `/feature-dev-aidd:researcher <ticket>` | Сбор исследовательского контекста перед планированием. |
| `/feature-dev-aidd:plan-new <ticket>` | Подготовка плана реализации. |
| `/feature-dev-aidd:review-spec <ticket>` | Сверка плана и PRD перед tasklist. |
| `/feature-dev-aidd:tasks-new <ticket>` | Формирование tasklist для реализации. |
| `/feature-dev-aidd:implement <ticket>` | Реализация задач по tasklist. |
| `/feature-dev-aidd:review <ticket>` | Ревью и фиксация замечаний по реализации. |
| `/feature-dev-aidd:qa <ticket>` | Финальная QA-проверка. |
| `/feature-dev-aidd:status [ticket]` | Быстрый статус текущего или указанного тикета. |

Опционально для loop-режима:
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_step.py --ticket TICKET-123`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_run.py --ticket TICKET-123 --max-iterations 5`

## Обновление
```text
/plugin update feature-dev-aidd@aidd-local
```
После обновления перезапустите сессию Claude Code.

## Диагностика
### После обновления не видны новые слэш-команды
1. Выполните `/plugin update feature-dev-aidd@aidd-local`.
2. Полностью перезапустите сессию Claude Code.

### Ошибка `ModuleNotFoundError: No module named 'aidd_runtime'`
1. Выполните `/plugin remove feature-dev-aidd@aidd-local`.
2. Выполните `/plugin install feature-dev-aidd@aidd-local`.
3. Перезапустите сессию Claude Code.

### Команды сообщают, что workspace не инициализирован
1. Выполните `/feature-dev-aidd:aidd-init`.
2. Проверьте окружение командой:
   `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-observability/runtime/doctor.py`

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
