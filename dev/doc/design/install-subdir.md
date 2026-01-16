# Установка workflow в поддиректорию `aidd/` (marketplace-only)

## Зачем
- Изолировать рабочие артефакты (`docs/`, `reports/`, `config/`) от корня продуктового репо.
- Развести плагин (commands/agents/hooks) и workspace (aidd/).
- Дать предсказуемую структуру для хуков и тестов без CLI-пэйлоада.

## Целевая структура
```
<repo>/
  .claude/
  .claude-plugin/
  agents/
  commands/
  hooks/
  dev/repo_tools/
  templates/
    aidd/
      config/
      docs/
      reports/
  aidd_runtime/
  aidd/            # появляется после /aidd-init
    config/
    docs/
    reports/
```

## Поведение init
- `/aidd-init` разворачивает `./aidd` из `templates/aidd` и не перезаписывает существующие файлы.
- Шаблоны обновляются через изменения в `templates/aidd/` + повторный `/aidd-init`.
- Smoke (`dev/repo_tools/smoke-workflow.sh`) использует текущий git checkout и hooks из `hooks/`.

## Сценарии установки
1) Marketplace:
   ```text
   /plugin marketplace add GrinRus/ai_driven_dev
   /plugin install feature-dev-aidd@aidd-local
   /aidd-init
   ```
2) Локальная разработка:
   ```bash
   PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli init
   ```
3) Обновление шаблонов:
   - Обновите плагин, затем повторите `/aidd-init`.
   - Сверьте изменения в `templates/aidd/` и перенесите их в рабочие артефакты при необходимости.

## Edge cases
- Если `aidd/` отсутствует, хуки и команды падают с явной подсказкой запустить `/aidd-init`.
- При нестандартном размещении плагина используйте `CLAUDE_PLUGIN_ROOT` для запуска скриптов вручную.

## Миграция из корня
1. Зафиксируйте локальные правки.
2. Удалите legacy-снапшоты из корня (`.claude`, `.claude-plugin`, `config`, `docs`, `dev/repo_tools`, `templates`).
3. Установите плагин через marketplace и выполните `/aidd-init`.
4. Перенесите артефакты в `aidd/docs` и `aidd/reports`.
5. Прогоните `dev/repo_tools/smoke-workflow.sh`.
