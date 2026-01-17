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
| `commands/` | Слэш-команды (RU) | Claude Code | runtime |
| `agents/` | Агентские промпты (RU) | Claude Code | runtime |
| `hooks/` | Gate/format/hooks | hooks.json | runtime |
| `dev/repo_tools/` | CI/smoke и вспомогательные утилиты | CI | dev-only |
| `tools/` | Runtime-скрипты | python entrypoints | runtime |
| `templates/aidd/` | Workspace-шаблоны (`docs/`, `reports/`, `config/`) | `/feature-dev-aidd:aidd-init` | docs |
| `dev/doc/` | ADR/дизайн/backlog | dev-only | dev-only |
| `dev/tests/` | Юнит/интеграционные тесты | CI | dev-only |

## Наблюдения
- Workspace `aidd/` не хранится в плагине; он создаётся из `templates/aidd/`.
- Repo-only tooling живёт в корне и не требуется пользователям.
- Крупные playbook/гайд‑документы остаются в `dev/doc/` и не входят в runtime.

## Решение
- Дистрибутив включает плагин, runtime и шаблоны `templates/aidd/`.
- Dev-only материалы остаются вне пользовательского workflow.
