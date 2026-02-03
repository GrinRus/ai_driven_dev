---
description: "План реализации по PRD + валидация"
argument-hint: "$1 [note...]"
lang: ru
prompt_version: 1.1.12
source_version: 1.1.12
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(sed:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/prd-check.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/research-check.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/feature-dev-aidd:plan-new` работает inline (без `context: fork`), потому что саб‑агенты не могут порождать других саб‑агентов. Команда фиксирует стадию `plan`, запускает `research-check`, пишет отдельные Context Pack для planner/validator и явно запускает саб‑агентов `feature-dev-aidd:planner` и `feature-dev-aidd:validator`. Свободный ввод после тикета используйте как уточнения для плана, включая блок `AIDD:ANSWERS` (если ответы уже есть).
Следуй attention‑policy из `aidd/AGENTS.md`, канону `aidd/docs/prompting/conventions.md` и начни с `aidd/docs/anchors/plan.md`.

## Входные артефакты
- `aidd/docs/prd/$1.prd.md` — статус `READY` обязателен.
- `aidd/docs/research/$1.md` — проверяется через `${CLAUDE_PLUGIN_ROOT}/tools/research-check.sh`.
- ADR (если есть) — архитектурные решения/ограничения.

## Evidence Read Policy (RLM-first)
- Primary evidence: `aidd/reports/research/<ticket>-rlm.pack.json` (pack-first summary).
- Slice on demand: `${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh --ticket <ticket> --query "<token>"`.
- Use raw `rg` only for spot-checks.
- Legacy `ast_grep` evidence is fallback-only.

## Когда запускать
- После `/feature-dev-aidd:idea-new` и `/feature-dev-aidd:researcher` (если он нужен), когда PRD готов.
- Повторный запуск — для актуализации плана при изменениях требований.

## Автоматические хуки и переменные
- `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh plan` фиксирует стадию `plan`.
- Команда должна запускать саб-агентов `feature-dev-aidd:planner` и `feature-dev-aidd:validator`.
- Перед запуском planner выполни `${CLAUDE_PLUGIN_ROOT}/tools/prd-check.sh --ticket $1`.
- Затем выполни `${CLAUDE_PLUGIN_ROOT}/tools/research-check.sh --ticket $1`.
- `gate-workflow` проверяет, что план/тасклист существуют до правок кода.

## Что редактируется
- `aidd/docs/plan/$1.md` — основной результат.

## Context Pack (шаблон)
- Шаблон: `aidd/reports/context/template.context-pack.md`.
- Файл planner: `aidd/reports/context/$1.planner.pack.md`.
- Файл validator: `aidd/reports/context/$1.validator.pack.md`.
- Paths: prd, arch_profile, research, plan, tasklist/spec/test_policy (if exists).
- What to do now: planner drafts macro-plan with iteration_id; validator validates executability.
- User note: $ARGUMENTS.
- При необходимости синхронизируй открытые вопросы/риски с PRD.

## Пошаговый план
1. Команда (до subagent): зафиксируй стадию `plan` через `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh plan` и активную фичу через `${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh "$1"`.
2. Команда (до subagent): запусти `${CLAUDE_PLUGIN_ROOT}/tools/prd-check.sh --ticket $1`; затем `${CLAUDE_PLUGIN_ROOT}/tools/research-check.sh --ticket $1` и остановись при ошибке.
3. Команда (до subagent): собери Context Pack `aidd/reports/context/$1.planner.pack.md` по шаблону `aidd/reports/context/template.context-pack.md`.
4. Команда → subagent: **Use the feature-dev-aidd:planner subagent. First action: Read `aidd/reports/context/$1.planner.pack.md`.**
5. Subagent (planner): обновляет план, учитывает `AIDD:ANSWERS`, закрывает вопросы в `AIDD:DECISIONS`.
6. Команда (до subagent validator): собери Context Pack `aidd/reports/context/$1.validator.pack.md` по шаблону `aidd/reports/context/template.context-pack.md`.
7. Команда → subagent: **Use the feature-dev-aidd:validator subagent. First action: Read `aidd/reports/context/$1.validator.pack.md`.**
8. Subagent (validator): проверяет исполняемость, возвращает `READY|BLOCKED`.

## Fail-fast и вопросы
- Нет READY PRD или `research-check` падает — остановись и попроси завершить предыдущие шаги.
- При `BLOCKED` от validator верни вопросы в формате `Вопрос N (Blocker|Clarification)` с `Зачем/Варианты/Default`.
- Если ответы приходят в чате — попроси блок `AIDD:ANSWERS` с форматом `Answer N: ...` (номер совпадает с `Вопрос N`).
- Если вопросы уже присутствуют/закрыты в PRD — не задавай их повторно, синхронизируй через `AIDD:OPEN_QUESTIONS` и `AIDD:DECISIONS`.

## Ожидаемый вывод
- `aidd/docs/plan/$1.md` обновлён и валидирован.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/feature-dev-aidd:plan-new ABC-123`
