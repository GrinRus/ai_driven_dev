# Аудит дистрибутива (plugin)

## Scope
- Плагин из корня репозитория (commands/agents/hooks + `.claude-plugin/*`)
- Шаблоны workspace в `templates/aidd/`
- Рантайм-скрипты `tools/`

## Критерии
- **Runtime**: используется хуками/командами/агентами во время работы пользователя.
- **Docs**: пользовательские инструкции и шаблоны, которые копируются в `aidd/`.
- **Dev-only**: инструменты поддержки и внутренние материалы.

## Инвентаризация (верхний уровень)

| Путь | Назначение | Используется | Статус |
| --- | --- | --- | --- |
| `.claude-plugin/marketplace.json` | Marketplace плагинов | Claude Code | runtime |
| `.claude-plugin/plugin.json` | Манифест плагина | Claude Code | runtime |
| `pyproject.toml`, `MANIFEST.in` | Packaging/метаданные | сборка/релизы | dev-only |
| `README.md`, `README.en.md`, `CHANGELOG.md`, `LICENSE`, `CONTRIBUTING.md` | Документация | GitHub/пользователи | repo-only |
| `commands/` | Слэш-команды (RU) | Claude Code | runtime |
| `agents/` | Агентские промпты (RU) | Claude Code | runtime |
| `hooks/` | Gate/format/hooks | hooks.json | runtime |
| `dev/repo_tools/` | CI/smoke и вспомогательные утилиты | CI | dev-only |
| `tools/` | Runtime-скрипты | python entrypoints | runtime |
| `templates/aidd/` | Workspace-шаблоны (`docs/`, `reports/`, `config/`) | `/feature-dev-aidd:aidd-init` | docs |
| `dev/doc/` | ADR/дизайн/backlog | dev-only | dev-only |
| `dev/tests/` | Юнит/интеграционные тесты | CI | dev-only |
| `dev/.github/` | CI workflows | GitHub Actions | dev-only |
| `.claude/` | Dogfooding для repo | локально | dev-only |
| `.tmp-debug/`, `build/`, `.pytest_cache/` | Локальные артефакты | локально | dev-only |

## Наблюдения
- Workspace `aidd/` не хранится в плагине; он создаётся из `templates/aidd/`.
- Repo-only tooling живёт в корне и не требуется пользователям.
- Крупные playbook/гайд‑документы остаются в `dev/doc/` и не входят в runtime.

## Решение
- Дистрибутив включает плагин, runtime и шаблоны `templates/aidd/`.
- Dev-only материалы остаются вне пользовательского workflow.

## Maintenance
- **Граница runtime vs dev-only:** runtime = `commands/`, `agents/`, `hooks/`, `tools/`, `.claude-plugin/`; шаблоны = `templates/aidd/`; dev-only = `dev/doc/`, `dev/tests/`, `dev/repo_tools/`.
- **Источник истины для шаблонов:** все правки делаются в `templates/aidd/`, `/feature-dev-aidd:aidd-init` идемпотентен.
- **Чистый корень:** dev-only материалы группируются под `dev/`, локальные артефакты не коммитятся.
- **Dev-only проверки:** `dev/repo_tools/ci-lint.sh`, `dev/repo_tools/smoke-workflow.sh`.
- **Перед релизом:** пересматривать этот аудит и обновлять инвентаризацию при изменениях структуры.
