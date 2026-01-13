# Аудит корня репозитория

## Scope
- Корень репозитория `ai_driven_dev`
- Цель: разделить dev-only артефакты и то, что действительно нужно в дистрибутиве

## Инвентаризация (корень)
| Путь | Назначение | Дистрибутив | Примечание |
| --- | --- | --- | --- |
| `src/claude_workflow_cli/` | Пакет CLI + payload | ship | основная кодовая база |
| `pyproject.toml`, `MANIFEST.in` | Packaging | ship | метаданные сборки |
| `README.md`, `README.en.md`, `CHANGELOG.md`, `LICENSE`, `CONTRIBUTING.md` | Документация | ship (repo) | README/CHANGELOG в PyPI/GitHub |
| `tools/` | Maintainer tooling | dev-only | проверки payload/миграции |
| `scripts/` | CI/линтеры/smoke | dev-only | используется в CI |
| `tests/` | Юнит/интеграционные тесты | dev-only | не входит в runtime |
| `doc/dev/` | ADR/дизайн/backlog | dev-only | не часть payload |
| `.github/` | CI workflows | dev-only | GitHub only |
| `.claude/` | Dogfooding для repo | dev-only | не часть payload |
| `.dev/`, `.tmp-debug/`, `build/`, `.pytest_cache/` | Локальные артефакты | dev-only | ignore |

## Наблюдения
- Документация для пользователей живет в `aidd/docs/**` внутри payload; `doc/dev/` — dev-only планирование.
- В корне нет `docs/` и `CLAUDE.md` — актуальные версии находятся в `aidd/`.
- Dev-only артефакты (tests/doc/dev) не должны попадать в payload/релизы.

## Вопросы
- Принято: dev-only материалы лежат в `doc/dev/`.
