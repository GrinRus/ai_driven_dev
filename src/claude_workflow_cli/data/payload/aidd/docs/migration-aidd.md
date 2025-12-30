# Миграция с корневого `.claude/docs` в `aidd/`

Инструкции для существующих установок, где payload развёрнут в корне репозитория.

1. Зафиксируйте локальные изменения (коммиты/бэкапы).
2. Удалите служебные снапшоты из корня: `.claude/`, `.claude-plugin/`, `claude-presets/`, `config/`, `docs/`, `prompts/`, `scripts/`, `templates/`, `tools/`, `workflow.md`. Продуктовый код и ваши артефакты оставьте.
3. Запустите `claude-workflow init --target . --commit-mode ticket-prefix` (добавьте `--enable-ci` по необходимости). Payload развернётся в `./aidd`.
4. Перенесите активные маркеры/артефакты:
   - `docs/.active_ticket` → `aidd/docs/.active_ticket`
   - `docs/.active_feature` → `aidd/docs/.active_feature`
   - `docs/prd|plan|research|tasklist/*` → соответствующие каталоги под `aidd/docs/`
   - отчёты из `reports/*` → `aidd/reports/*` (по необходимости)
5. Перегенерируйте контекст Researcher при сомнениях: `claude-workflow research --target . --ticket <ticket> --auto`.
6. Запустите `aidd/scripts/smoke-workflow.sh` или `claude-workflow smoke` для проверки гейтов.

**Если CLI не найден:** установите через `uv tool install claude-workflow-cli --from git+https://github.com/GrinRus/ai_driven_dev.git` и повторите init. Все команды и хуки ожидают структуру `./aidd/**`.
