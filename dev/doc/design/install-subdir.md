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
  tools/
  dev/repo_tools/
  templates/
    aidd/
      config/
      docs/
      reports/
  aidd/            # появляется после /feature-dev-aidd:aidd-init
    config/
    docs/
    reports/
```

## Поведение init
- `/feature-dev-aidd:aidd-init` разворачивает `./aidd` из `templates/aidd` и не перезаписывает существующие файлы.
- Шаблоны обновляются через изменения в `templates/aidd/` + повторный `/feature-dev-aidd:aidd-init`.
- Smoke (`dev/repo_tools/smoke-workflow.sh`) использует текущий git checkout и hooks из `hooks/`.

## Сценарии установки
1) Marketplace:
   ```text
   /plugin marketplace add GrinRus/ai_driven_dev
   /plugin install feature-dev-aidd@aidd-local
   /feature-dev-aidd:aidd-init
   ```
2) Локальная разработка:
   ```bash
   ${CLAUDE_PLUGIN_ROOT}/tools/init.sh
   ```
3) Обновление шаблонов:
   - Обновите плагин, затем повторите `/feature-dev-aidd:aidd-init`.
   - Сверьте изменения в `templates/aidd/` и перенесите их в рабочие артефакты при необходимости.

## Edge cases
- Если `aidd/` отсутствует, хуки и команды падают с явной подсказкой запустить `/feature-dev-aidd:aidd-init`.
- При нестандартном размещении плагина используйте `CLAUDE_PLUGIN_ROOT` для запуска скриптов вручную.

## Миграция из корня
1. Зафиксируйте локальные правки.
2. Удалите legacy-снапшоты из корня (`.claude`, `.claude-plugin`, `config`, `docs`, `dev/repo_tools`, `templates`).
3. Установите плагин через marketplace и выполните `/feature-dev-aidd:aidd-init`.
4. Перенесите артефакты в `aidd/docs` и `aidd/reports`.
5. Прогоните `dev/repo_tools/smoke-workflow.sh`.
