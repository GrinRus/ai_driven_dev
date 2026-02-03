---
description: "Spec interview (AskUserQuestionTool) → spec.yaml (tasklist обновляется через /feature-dev-aidd:tasks-new)"
argument-hint: "$1 [note...]"
lang: ru
prompt_version: 1.0.11
source_version: 1.0.11
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - AskUserQuestionTool
  - "Bash(rg:*)"
  - "Bash(sed:*)"
  - "Bash(cat:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/feature-dev-aidd:spec-interview` работает inline: проводит интервью на верхнем уровне (AskUserQuestionTool), записывает лог интервью, пишет Context Pack для writer‑агента и явно запускает саб‑агента **feature-dev-aidd:spec-interview-writer**. Спека хранится в `aidd/docs/spec/$1.spec.yaml`. Обновление tasklist выполняется только через `/feature-dev-aidd:tasks-new`.
Следуй attention‑policy из `aidd/AGENTS.md`, канону `aidd/docs/prompting/conventions.md` и начни с `aidd/docs/anchors/spec-interview.md`.

## Входные артефакты
- `aidd/docs/plan/$1.md`
- `aidd/docs/prd/$1.prd.md`
- `aidd/docs/research/$1.md`
- `aidd/docs/spec/template.spec.yaml`

## Evidence Read Policy (RLM-first)
- Primary evidence: `aidd/reports/research/<ticket>-rlm.pack.json` (pack-first summary).
- Slice on demand: `${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh --ticket <ticket> --query "<token>"`.
- Use raw `rg` only for spot-checks.
- Legacy `ast_grep` evidence is fallback-only.

## Когда запускать
- После `/feature-dev-aidd:review-spec` (опционально).
- Можно запускать **до** `/feature-dev-aidd:tasks-new` или **после** для дополнительного уточнения.
- Повторно — для следующей волны интервью/уточнений.

## Автоматические хуки и переменные
- `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh spec-interview` фиксирует стадию `spec-interview`.
- `${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh $1` фиксирует активную фичу.
- AskUserQuestionTool используется только здесь (не в саб-агентах).

## Что редактируется
- `aidd/docs/spec/$1.spec.yaml`
- `aidd/reports/spec/$1.interview.jsonl`

## Context Pack (шаблон)
- Шаблон: `aidd/reports/context/template.context-pack.md`.
- Целевой файл: `aidd/reports/context/$1.spec-interview.pack.md` (stage/agent/paths/what-to-do заполняются под spec-interview).
- Paths: plan, tasklist (if exists), prd, arch_profile, spec, research, interview_log, test_policy (if exists).
- What to do now: build spec.yaml from interview log, fill iteration_decisions.
- User note: $ARGUMENTS.

## Пошаговый план
1. Команда (до subagent): зафиксируй стадию `spec-interview` через `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh spec-interview` и активную фичу через `${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh "$1"`.
2. Команда (до subagent): прочитай plan/PRD/research и собери decision points по `iteration_id`.
3. Команда (до subagent): проведи интервью через AskUserQuestionTool (non-obvious вопросы) по каждой итерации:
   - Data/compat/idempotency → Contracts/errors → UX states → Tradeoffs → Tests → Rollout/Obs.
4. Команда (до subagent): запиши ответы в `aidd/reports/spec/$1.interview.jsonl` (append-only).
5. Команда (до subagent): собери Context Pack `aidd/reports/context/$1.spec-interview.pack.md` по шаблону `aidd/reports/context/template.context-pack.md`.
6. Команда → subagent: **Use the feature-dev-aidd:spec-interview-writer subagent. First action: Read `aidd/reports/context/$1.spec-interview.pack.md`.**
7. Subagent: формирует/обновляет `aidd/docs/spec/$1.spec.yaml` по шаблону.
8. Обнови tasklist только через `/feature-dev-aidd:tasks-new` (обязательный шаг для синхронизации).

## Fail-fast и вопросы
- Нет plan/PRD/research — остановись и попроси завершить `/feature-dev-aidd:plan-new` или `/feature-dev-aidd:review-spec`.
- Если AskUserQuestionTool недоступен — попроси пользователя запустить интервью вручную и записать ответы.

## Ожидаемый вывод
- `aidd/docs/spec/$1.spec.yaml` создан/обновлён.
- `aidd/reports/spec/$1.interview.jsonl` обновлён.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/feature-dev-aidd:spec-interview ABC-123`
