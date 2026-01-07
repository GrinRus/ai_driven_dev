# Установка workflow в поддиректорию `aidd/`

## Зачем
- Изолировать служебные артефакты (команды, агенты, хуки, шаблоны, конфиги) от корня продуктового репо.
- Облегчить обновление payload через `claude-workflow init/sync/upgrade` без коллизий с пользовательскими файлами.
- Поддержать сценарии многопроектной установки (несколько `aidd/` в одном воркспейсе).
- Дать предсказуемый runtime в smoke/pytest: всё берётся из одного payload-префикса, без корневых снапшотов.

## Целевая структура
```
<workspace>/
  .claude/
  .claude-plugin/
  aidd/
    .claude-plugin/
    agents/
    commands/
    hooks/
    config/
    docs/
    reports/
    scripts/
    templates/
    tools/
```

## Поведение CLI
- Дефолт: `claude-workflow init --target .` создаёт `<cwd>/aidd/` по manifest (префикс `aidd/` внутри ресурса).
- `--target` задаёт корень установки; внутри него всегда создаётся поддиректория `aidd/` (перемещённые fallback/зеркалирование в корень убраны).
- `sync/upgrade` работают только с вложенным payload; dry-run не создаёт каталог и показывает diff по manifest.
- При наличии старых `.claude/` и `.claude-plugin/` в корне CLI предупреждает и предлагает миграцию; существующий `aidd/` обновляется на месте с бэкапом изменённых файлов.
- Smoke из CLI (`claude-workflow smoke`) и bash-скрипт `scripts/smoke-workflow.sh` используют тот же payload и запускают e2e в tmp-каталоге из текущего git checkout, без скачивания внешних артефактов.

## Сценарии установки
1) Быстрый старт через uv:
   ```bash
   uv tool install --force "git+https://github.com/GrinRus/ai_driven_dev.git#egg=claude-workflow-cli"
   claude-workflow init --target .
   claude-workflow smoke          # e2e из текущей ветки, tmp-каталог
   ```
2) Локальный payload (dogfooding/ветка):
   ```bash
   CLAUDE_TEMPLATE_DIR=./src/claude_workflow_cli/data/payload/aidd \
   claude-workflow init --target .
   ```
3) Повторная установка/upgrade:
   - `claude-workflow upgrade --target .` для обновления неизменённых файлов.
   - `claude-workflow sync --direction=from-root` при подготовке релиза (зеркалит корневые снапшоты в payload).

## Edge cases и DX
- Несколько `aidd/` в монорепо: CLI работает с ближайшим к `--target`; smoke принимает `--target` и не ходит выше по дереву.
- CI: команды `claude-workflow init/smoke` должны выполняться из корня продукта; PYTHONPATH выставляется автоматически на время прогона.
- Бэкапы: изменённые файлы пишутся с суффиксом `.bak` при upgrade/sync, отчёт — в stdout.
- Контроль целостности: `tools/check_payload_sync.py` сравнивает манифест и runtime; тесты используют payload из пакета, не корневые снапшоты.
- Неверный таргет/рабочая директория: запуск CLI/хуков вне `aidd/` приводит к явной ошибке «aidd/docs not found», fallback в корень отключён.

## Миграция из корня
1. Зафиксировать локальные правки (при необходимости `scripts/sync-payload.sh --direction=from-root` для отражения в payload).
2. Удалить dev-снапшоты из корня (`.claude`, `.claude-plugin`, `config`, `docs`, `scripts`, `templates`, `tools`), оставить продуктовые файлы.
3. Запустить `claude-workflow init --target .` (или с `CLAUDE_TEMPLATE_DIR=...` для локальной ветки) — создаст `aidd/`.
4. Прогнать `claude-workflow smoke` (или `scripts/smoke-workflow.sh`) — e2e на tmp-каталоге из текущей ветки.
5. Обновить CI шаги: init/smoke должны указывать `--target .` и работать с `aidd/`.

## To-do
- Добавить схемы путей (`--target`, `CLAUDE_TEMPLATE_DIR`, `PYTHONPATH` в smoke).
- Зафиксировать политику для нескольких `aidd/` в одном repo (порядок поиска target).
- Финализировать user-facing walkthrough в `doc/dev/workflow.md`/`README*` с примерами команд под новую структуру.
