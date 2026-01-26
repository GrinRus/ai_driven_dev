---
description: "Развёртывание инфраструктуры AIDD в ./aidd"
argument-hint: "[--force] [--detect-build-tools] [--detect-stack]"
lang: ru
prompt_version: 0.1.3
source_version: 0.1.3
allowed-tools:
  - Read
  - Write
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/init.sh:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
`/feature-dev-aidd:aidd-init` разворачивает рабочую директорию `./aidd` из шаблонов `templates/aidd` и тонкие root‑адаптеры из `templates/root`. Команда копирует отсутствующие файлы и каталоги, не перезаписывая пользовательские изменения (без `--force`). Опционально можно заполнить `.claude/settings.json` шаблонами `automation.tests` через `--detect-build-tools` и заполнить Architecture Profile stack‑hint через `--detect-stack`.

## Входные артефакты
- `templates/aidd/**` — источник шаблонов.
- `templates/root/**` — root‑адаптеры (AGENTS/CLAUDE/Cursor/Copilot).

## Когда запускать
- сразу после установки плагина через marketplace;
- если в проекте отсутствует `./aidd`.

## Автоматические хуки и переменные
- Используется `CLAUDE_PLUGIN_ROOT` для поиска `templates/aidd` и runtime‑скриптов в `tools/`.
- Дополнительных хуков нет.

## Что редактируется
- создаётся `aidd/**` в корне workspace.
- создаются root‑адаптеры в корне workspace (если отсутствуют).

## Пошаговый план
1. Запусти `${CLAUDE_PLUGIN_ROOT}/tools/init.sh` (опционально `--force`).
2. Убедись, что появились `aidd/docs`, `aidd/reports`, `aidd/docs/{prd,plan,tasklist}`.
3. При необходимости добавь `--detect-build-tools`, чтобы заполнить `.claude/settings.json` дефолтами для `automation.tests`.
4. При необходимости добавь `--detect-stack`, чтобы заполнить `aidd/docs/architecture/profile.md` stack‑hint и skills.

## Fail-fast и вопросы
- Если `templates/aidd` не найден — переустановите плагин и повторите `/feature-dev-aidd:aidd-init`.
- Если нет прав на запись в workspace — запросите доступ и повторите команду.

## Ожидаемый вывод
- Сообщение `copied N files` при первом запуске.
- Сообщение `no changes` при повторном запуске без `--force`.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `${CLAUDE_PLUGIN_ROOT}/tools/init.sh`
- `${CLAUDE_PLUGIN_ROOT}/tools/init.sh --force`
- `${CLAUDE_PLUGIN_ROOT}/tools/init.sh --detect-build-tools`
- `${CLAUDE_PLUGIN_ROOT}/tools/init.sh --detect-stack`
