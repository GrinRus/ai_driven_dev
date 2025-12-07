# Установка workflow в поддиректорию `aidd/`

## Зачем
- Изолировать служебные артефакты (команды, агенты, хуки, пресеты, шаблоны, конфиги) от корня продуктового репо.
- Облегчить обновление payload через `claude-workflow init/sync/upgrade` без коллизий с пользовательскими файлами.
- Поддержать сценарии многопроектной установки (несколько `aidd/` в одном воркспейсе).

## Целевая структура
```
<workspace>/
  aidd/
    .claude/
    claude-presets/
    config/
    docs/
    prompts/
    scripts/
    templates/
    tools/
    workflow.md
```

## Сценарии установки
- Базовый: `claude-workflow init --target .` → создаёт/обновляет `<cwd>/aidd/` из payload (manifest-проверки, бэкапы, версионирование).
- Переопределение: `--target /path/to/ws` + `CLAUDE_TEMPLATE_DIR` для локального payload.
- Sync/upgrade: `claude-workflow sync` / `upgrade` работают относительно `aidd/`, поддерживают `--include` и префикс из manifest.

## Совместимость / DX
- Dry-run не создаёт каталог `aidd/`, только показывает diff по manifest.
- Готовый проект содержит `aidd/.claude/.template_version`; CLI предупреждает, если версия отстаёт.
- Хуки и команды запускаются из `aidd/` (PYTHONPATH/ROOT_DIR подставляется автоматически).

## To-do
- Добавить схемы/диаграмму путей (`--workspace-root`, `--target`, `CLAUDE_TEMPLATE_DIR`).
- Выписать edge-cases: существующий `.claude` в корне, несколько `aidd/`, CI-пайплайн с кастомным `cwd`.
- Миграция из корня:
  1. Зафиксировать локальные правки (`git status`, при необходимости `scripts/sync-payload.sh --direction=from-root`).
  2. Очистить dev-снапшот (`rm -rf .claude claude-presets config docs prompts scripts templates tools workflow.md`), оставить продуктовые файлы.
  3. Запустить `claude-workflow init --target .` → создаст `aidd/` с полным payload.
  4. Проверить smoke/pytest, обновить CI/CD шаги на `aidd/`.
