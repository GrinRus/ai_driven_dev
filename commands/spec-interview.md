---
description: "Spec interview (AskUserQuestionTool) → spec.yaml (tasklist обновляется через /feature-dev-aidd:tasks-new)"
argument-hint: "<TICKET> [note...]"
lang: ru
prompt_version: 1.0.0
source_version: 1.0.0
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - AskUserQuestionTool
  - "Bash(rg:*)"
  - "Bash(sed:*)"
  - "Bash(cat:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/feature-dev-aidd:spec-interview` проводит интервью на верхнем уровне (AskUserQuestionTool), записывает лог интервью и формирует spec-файл. Спека хранится в `aidd/docs/spec/<ticket>.spec.yaml`. Обновление tasklist выполняется только через `/feature-dev-aidd:tasks-new`.
Следуй attention‑policy из `aidd/AGENTS.md` и начни с `aidd/docs/anchors/spec-interview.md`.

## Входные артефакты
- `@aidd/docs/plan/<ticket>.md`
- `@aidd/docs/prd/<ticket>.prd.md`
- `@aidd/docs/research/<ticket>.md`
- `@aidd/docs/spec/template.spec.yaml`

## Когда запускать
- После `/feature-dev-aidd:review-spec` (опционально).
- Можно запускать **до** `/feature-dev-aidd:tasks-new` или **после** для дополнительного уточнения.
- Повторно — для следующей волны интервью/уточнений.

## Автоматические хуки и переменные
- `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh spec-interview` фиксирует стадию `spec-interview`.
- `${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh --target . <ticket>` фиксирует активную фичу.
- AskUserQuestionTool используется только здесь (не в саб-агентах).

## Что редактируется
- `aidd/docs/spec/<ticket>.spec.yaml`
- `aidd/reports/spec/<ticket>.interview.jsonl`

## Пошаговый план
1. Зафиксируй стадию `spec-interview` и активную фичу.
2. Прочитай plan/PRD/research и собери decision points по `iteration_id`.
3. Проведи интервью через AskUserQuestionTool (non-obvious вопросы) по каждой итерации:
   - Data/compat/idempotency → Contracts/errors → UX states → Tradeoffs → Tests → Rollout/Obs.
4. Запиши ответы в `aidd/reports/spec/<ticket>.interview.jsonl` (append-only).
5. Сформируй/обнови `aidd/docs/spec/<ticket>.spec.yaml` по шаблону.
6. Если нужна синтезация по логу — запусти саб-агента `spec-interview-writer`.
7. Обнови tasklist только через `/feature-dev-aidd:tasks-new` (обязательный шаг для синхронизации).

## Fail-fast и вопросы
- Нет plan/PRD/research — остановись и попроси завершить `/feature-dev-aidd:plan-new` или `/feature-dev-aidd:review-spec`.
- Если AskUserQuestionTool недоступен — попроси пользователя запустить интервью вручную и записать ответы.

## Ожидаемый вывод
- `aidd/docs/spec/<ticket>.spec.yaml` создан/обновлён.
- `aidd/reports/spec/<ticket>.interview.jsonl` обновлён.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/feature-dev-aidd:spec-interview ABC-123`
