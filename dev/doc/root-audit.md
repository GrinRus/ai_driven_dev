# Аудит корня репозитория

## Scope
- Корень репозитория `ai_driven_dev`
- Цель: разделить dev-only артефакты и то, что действительно нужно в дистрибутиве

## Инвентаризация (корень)

| Путь | Назначение | Дистрибутив | Примечание |
| --- | --- | --- | --- |
| `tools/` | Runtime-скрипты (Python entrypoints) | ship | основная кодовая база |
| `commands/`, `agents/`, `hooks/` | Плагин (prompts + hooks) | ship | runtime Claude Code |
| `templates/aidd/` | Workspace-шаблоны | ship | для `/feature-dev-aidd:aidd-init` |
| `dev/repo_tools/` | Smoke/CI и dev-утилиты | dev-only | не используется в runtime |
| `.claude-plugin/` | Marketplace + plugin manifest | ship | установка плагина |
| `pyproject.toml`, `MANIFEST.in` | Packaging | ship | метаданные сборки |
| `README.md`, `README.en.md`, `CHANGELOG.md`, `LICENSE`, `CONTRIBUTING.md` | Документация | ship (repo) | README/CHANGELOG в GitHub |
| `dev/tests/` | Юнит/интеграционные тесты | dev-only | CI-only |
| `dev/doc/` | ADR/дизайн/backlog | dev-only | планирование |
| `dev/.github/` | CI workflows | dev-only | GitHub only |
| `.claude/` | Dogfooding для repo | dev-only | не часть плагина |
| `.tmp-debug/`, `build/`, `.pytest_cache/` | Локальные артефакты | dev-only | ignore |

## Наблюдения
- Пользовательские артефакты создаются в `aidd/` через `/feature-dev-aidd:aidd-init` и не хранятся в репозитории как источник истины.
- Dev-only артефакты (`dev/tests`, `dev/doc`) не должны попадать в дистрибутив.

## Вопросы
- Принято: dev-only материалы лежат в `dev/doc/`.
