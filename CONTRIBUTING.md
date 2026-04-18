# Contributing

Короткий operational guide для вкладов.

## Typical change flow
1. Создайте рабочую ветку.
2. Следуйте repo contract из `AGENTS.md`.
3. Прогоните обязательные проверки:
   - `tests/repo_tools/ci-lint.sh`
   - `tests/repo_tools/smoke-workflow.sh`
   - `python3 tests/repo_tools/release_guard.py --root .` для release-правок
4. Обновите публичные docs и `CHANGELOG.md`, если поведение изменилось.
5. Для release PR синхронизируйте `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `CHANGELOG.md`.

## Release essentials
1. Подготовьте release PR: версия в `.claude-plugin/plugin.json`, immutable `vX.Y.Z` ref и версия в `.claude-plugin/marketplace.json`, heading `## X.Y.Z - YYYY-MM-DD` в `CHANGELOG.md`.
2. После merge создайте annotated tag `vX.Y.Z` на merge commit и push.
3. Публикацию и parity checks выполняет `.github/workflows/release-self-hosted.yml`.

## Invariants
- Канонические артефакты плагина: `skills/`, `agents/`, `hooks/`, `.claude-plugin/`.
- Workspace-шаблоны: `templates/aidd/` (копируются через `/feature-dev-aidd:aidd-init`).
- Canonical runtime API: `python3 skills/*/runtime/*.py`.
- `tools/*.sh` не является runtime API.

Полный maintainer process: `AGENTS.md`. Release checklist: `docs/runbooks/marketplace-release.md`.
