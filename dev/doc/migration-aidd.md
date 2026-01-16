# Миграция на marketplace-only AIDD

Инструкции для существующих установок, где legacy payload развёрнут в корне репозитория.

1. Зафиксируйте локальные изменения (коммиты/бэкапы).
2. Удалите legacy-снапшоты из корня: `.claude/`, `.claude-plugin/`, `config/`, `docs/`, `dev/repo_tools/`, `templates/`. Продуктовый код и ваши артефакты оставьте.
3. Установите плагин через marketplace и запустите `/aidd-init` — появится `./aidd`.
4. Перенесите активные маркеры/артефакты:
   - `docs/.active_ticket` → `aidd/docs/.active_ticket`
   - `docs/.active_feature` → `aidd/docs/.active_feature`
   - `docs/prd|plan|research|tasklist/*` → соответствующие каталоги под `aidd/docs/`
   - отчёты из `reports/*` → `aidd/reports/*` (по необходимости)
5. Перегенерируйте контекст Researcher при сомнениях: `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli research --ticket <ticket> --auto`.
6. Запустите smoke-проверку в репозитории: `dev/repo_tools/smoke-workflow.sh`.
