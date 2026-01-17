---
description: "Развёртывание инфраструктуры AIDD в ./aidd"
argument-hint: "[--force]"
lang: ru
prompt_version: 0.1.0
source_version: 0.1.0
allowed-tools:
  - Read
  - Write
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/init.sh:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
`/feature-dev-aidd:aidd-init` разворачивает рабочую директорию `./aidd` из шаблонов `templates/aidd`. Команда копирует отсутствующие файлы и каталоги, не перезаписывая пользовательские изменения (без `--force`).

## Входные артефакты
- `templates/aidd/**` — источник шаблонов.

## Когда запускать
- сразу после установки плагина через marketplace;
- если в проекте отсутствует `./aidd`.

## Автоматические хуки и переменные
- Используется `CLAUDE_PLUGIN_ROOT` для поиска `templates/aidd` и runtime‑скриптов в `tools/`.
- Дополнительных хуков нет.

## Что редактируется
- создаётся `aidd/**` в корне workspace.

## Пошаговый план
1. Запусти `${CLAUDE_PLUGIN_ROOT}/tools/init.sh` (опционально `--force`).
2. Убедись, что появились `aidd/docs`, `aidd/reports`, `aidd/docs/{prd,plan,tasklist}`.

## Fail-fast и вопросы
- Если `templates/aidd` не найден — переустановите плагин и повторите `/feature-dev-aidd:aidd-init`.
- Если нет прав на запись в workspace — запросите доступ и повторите команду.

## Ожидаемый вывод
- Сообщение `copied N files` при первом запуске.
- Сообщение `no changes` при повторном запуске без `--force`.

## Примеры CLI
- `${CLAUDE_PLUGIN_ROOT}/tools/init.sh`
- `${CLAUDE_PLUGIN_ROOT}/tools/init.sh --force`
