# Contributing

Короткий и практичный гайд для вкладов в репозиторий.

## Как внести изменения
1. Форкните репозиторий и создайте ветку под задачу.
2. Следуйте процессу в `AGENTS.md` (agent-first, порядок стадий, артефакты).
3. Прогоните проверки:
   - `tests/repo_tools/ci-lint.sh`
   - `tests/repo_tools/smoke-workflow.sh` (обязательно при runtime изменениях; в CI job запускается всегда и auto-skip'ается при отсутствии runtime diff)
   - `python3 tests/repo_tools/release_guard.py --root .` (обязательно для release-правок)
4. Обновите документацию:
   - `README.md` + `README.en.md` (и поле _Last sync_)
   - `AGENTS.md` при изменении поведения
5. Обновите `CHANGELOG.md` в секции **Unreleased** при изменении поведения.
6. Для release PR синхронизируйте `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `CHANGELOG.md`.

## Self-hosted release process (GitHub, tag-driven)
1. Подготовьте release PR:
   - `version = X.Y.Z` в `.claude-plugin/plugin.json`;
   - `plugins[].version = X.Y.Z` и `plugins[].source.ref = vX.Y.Z` в `.claude-plugin/marketplace.json`;
   - release heading `## X.Y.Z - YYYY-MM-DD` в `CHANGELOG.md`.
2. В `main` допускается только immutable `source.ref` формата `vX.Y.Z` (ветки `main/feature/*` запрещены).
3. После merge создайте аннотированный tag `vX.Y.Z` на merge commit и запушьте его.
4. Tag запускает `.github/workflows/release-self-hosted.yml`, который проверяет parity и публикует GitHub Release.
5. В GitHub Settings включите tag protection/ruleset для `v*` (запрет force-update/delete).

## Что важно помнить
- Канонические артефакты плагина: `skills/`, `agents/`, `hooks/`, `.claude-plugin/`.
- Workspace-шаблоны: `templates/aidd/` (копируются через `/feature-dev-aidd:aidd-init`).
- Canonical runtime API: `python3 skills/*/runtime/*.py`.
- `tools/*.sh` не является runtime API.

Полный процесс и проверки описаны в `AGENTS.md`.
