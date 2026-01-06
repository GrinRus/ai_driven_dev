# Аудит дистрибутива (payload)

## Scope
- `src/claude_workflow_cli/data/payload/**`
- Собранный payload (workspace `.claude/`, `.claude-plugin/` + плагин `aidd/`)

## Критерии
- **Runtime**: используется хуками/командами/агентами/CLI во время работы пользователя.
- **Docs**: пользовательские инструкции и шаблоны.
- **Dev-only**: инструменты поддержания payload/релизов, не требуются в обычном проекте.

## Инвентаризация (верхний уровень)
| Путь | Назначение | Используется | Статус |
| --- | --- | --- | --- |
| `.claude/settings.json` | Права/automation workspace | хуки/CLI | runtime |
| `.claude/cache/.gitkeep` | Placeholder кеша | хуки | runtime |
| `.claude-plugin/marketplace.json` | Marketplace плагинов | Claude Code | runtime |
| `aidd/.claude-plugin/plugin.json` | Манифест плагина | Claude Code | runtime |
| `aidd/agents/` | Агентские промпты (RU) | команды/агенты | runtime |
| `aidd/agents/templates/` | Шаблоны промптов агентов | maintainers | docs |
| `aidd/commands/` | Слэш-команды (RU) | Claude Code | runtime |
| `aidd/commands/templates/` | Шаблоны промптов команд | maintainers | docs |
| `aidd/hooks/` | Gate/format/hooks | hooks.json | runtime |
| `aidd/hooks/_vendor/` | Вендорные Python-модули | хуки | runtime |
| `aidd/config/` | Конвенции/гейты | хуки/CLI | runtime |
| `aidd/docs/` | Core docs + шаблоны артефактов (sdlc/status + `docs/*/template.md`) | пользователи | docs |
| `aidd/templates/` | Git hook samples | CLI | runtime/docs |
| `aidd/scripts/context_gc/` | Context GC hooks | hooks.json | runtime |
| `aidd/scripts/gradle/init-print-projects.gradle` | Selective tests | format-and-test | runtime |
| `aidd/scripts/qa-agent.py` | QA агент | gate-qa/`/qa` | runtime |
| `aidd/scripts/prd-review-agent.py` | PRD review агент | gate-prd-review | runtime |
| `aidd/scripts/prd_review_gate.py` | PRD gate логика | hooks | runtime |
| `aidd/scripts/smoke-workflow.sh` | E2E smoke | CI/maintainers | dev-only? |
| `aidd/tools/run_cli.py` | Helper запуска CLI | хуки/скрипты | runtime |
| `aidd/tools/set_active_feature.py` | Активный ticket/PRD | `/idea-new` | runtime |
| `aidd/tools/researcher_context.py` | Контекст для research | CLI | runtime |

## Наблюдения
- Workspace `.claude/` и `.claude-plugin/` живут вне `aidd/`, поэтому audit/sync должен учитывать два корня.
- Repo-only tooling: `scripts/sync-payload.sh`, `scripts/lint-prompts.py`, `scripts/prompt-version`, `tools/check_payload_sync.py`, `tools/prompt_diff.py`, `tools/payload_audit.py` вынесены в корень репозитория.
- Крупные playbook/гайд‑документы перенесены в `doc/dev/` и не входят в payload.

## Решение
- Payload содержит только runtime/docs артефакты; repo-only tooling живёт в корне и не входит в дистрибутив.
