# Contributing

Короткий и практичный гайд для вкладов в репозиторий.

## Как внести изменения
1. Форкните репозиторий и создайте ветку под задачу.
2. Следуйте процессу в `AGENTS.md` (agent-first, порядок стадий, артефакты).
3. Прогоните проверки:
   - `tests/repo_tools/ci-lint.sh`
   - `tests/repo_tools/smoke-workflow.sh` (если менялись runtime/хуки/команды)
4. Обновите документацию:
   - `README.md` + `README.en.md` (и поле _Last sync_)
   - `AGENTS.md` при изменении поведения
5. Обновите `CHANGELOG.md` в секции **Unreleased** при изменении поведения.

## Что важно помнить
- Канонические артефакты плагина: `commands/`, `agents/`, `hooks/`, `tools/`.
- Workspace-шаблоны: `templates/aidd/` (копируются через `/feature-dev-aidd:aidd-init`).
- Runtime запускается как `${CLAUDE_PLUGIN_ROOT}/tools/*.sh`.

Полный процесс и проверки описаны в `AGENTS.md`.
