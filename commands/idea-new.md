---
description: "Инициация фичи: setup ticket/slug → analyst → PRD draft + вопросы"
argument-hint: "$1 [slug=<slug-hint>] [note...]"
lang: ru
prompt_version: 1.3.13
source_version: 1.3.13
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(sed:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/analyst-check.sh:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
`/feature-dev-aidd:idea-new` работает inline: фиксирует активный ticket/slug-hint, выставляет стадию `idea`, собирает контекст в Context Pack и явно запускает саб‑агента **feature-dev-aidd:analyst**. Аналитик формирует PRD draft с вопросами и заполняет `## AIDD:RESEARCH_HINTS`. После ответов пользователя следующий обязательный шаг — `/feature-dev-aidd:researcher $1`; READY ставится после ответов. Свободный ввод после тикета используется как заметка для PRD.
Следуй attention‑policy из `aidd/AGENTS.md` и начни с `aidd/docs/anchors/idea.md`.

## Входные артефакты
- `aidd/docs/prd/template.md` — шаблон PRD (Status: draft, `## Диалог analyst`).
- `aidd/docs/research/$1.md`, `aidd/reports/research/*` — если уже есть, использовать как контекст.
- `aidd/docs/.active_ticket`, `aidd/docs/.active_feature` — активные маркеры.

## Evidence Read Policy (RLM-first)
- Primary evidence: `aidd/reports/research/<ticket>-rlm.pack.*` (pack-first summary).
- Slice on demand: `${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh --ticket <ticket> --query "<token>"`.
- Use raw `rg` only for spot-checks.
- Legacy `ast_grep` evidence is fallback-only.

## Когда запускать
- В начале работы над фичей, до плана/кода.
- Повторно — когда нужно обновить PRD и вопросы.

## Автоматические хуки и переменные
- `${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh` синхронизирует `.active_*` и scaffold'ит PRD.
- `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh idea` фиксирует стадию `idea`.
- Команда должна запускать саб-агента **feature-dev-aidd:analyst**.
- `${CLAUDE_PLUGIN_ROOT}/tools/analyst-check.sh --ticket $1` — проверка диалога/статуса после ответов.

## Что редактируется
- `aidd/docs/.active_ticket`, `aidd/docs/.active_feature`.
- `aidd/docs/prd/$1.prd.md`.

## Context Pack (шаблон)
Файл: `aidd/reports/context/$1.idea.pack.md`.

```md
# AIDD Context Pack — idea
ticket: $1
stage: idea
agent: feature-dev-aidd:analyst
generated_at: <UTC ISO-8601>

## Paths
- prd: aidd/docs/prd/$1.prd.md
- arch_profile: aidd/docs/architecture/profile.md
- research: aidd/docs/research/$1.md (if exists)
- plan: aidd/docs/plan/$1.md (if exists)
- tasklist: aidd/docs/tasklist/$1.md (if exists)
- spec: aidd/docs/spec/$1.spec.yaml (if exists)
- test_policy: aidd/.cache/test-policy.env (if exists)

## What to do now
- Draft PRD, fill AIDD:RESEARCH_HINTS, ask questions.

## User note
- $ARGUMENTS (excluding slug=...)

## Git snapshot (optional)
- branch: <git rev-parse --abbrev-ref HEAD>
- diffstat: <git diff --stat>
```

## Пошаговый план
1. Команда (до subagent): зафиксируй стадию `idea`: `${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh idea`.
2. Команда (до subagent): зафиксируй активный тикет/slug: `${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh "$1" [--slug-note "<slug>"]` (slug берётся из аргумента `slug=<...>`, заметка = `$ARGUMENTS` без `slug=...`).
3. Команда (до subagent): собери Context Pack `aidd/reports/context/$1.idea.pack.md` по шаблону W79-10.
4. Команда → subagent: **Use the feature-dev-aidd:analyst subagent. First action: Read `aidd/reports/context/$1.idea.pack.md`.**
5. Subagent: обновляет PRD, заполняет `## AIDD:RESEARCH_HINTS`, формирует вопросы; при наличии `AIDD:ANSWERS` синхронизирует `AIDD:OPEN_QUESTIONS`/`AIDD:DECISIONS`.
6. Команда (после subagent): если ответы уже есть — запусти `${CLAUDE_PLUGIN_ROOT}/tools/analyst-check.sh --ticket $1`.
7. Верни список вопросов и статус PRD; следующий шаг — `/feature-dev-aidd:researcher $1`, затем `/feature-dev-aidd:plan-new`.

## Fail-fast и вопросы
- Нет тикета — остановись и запроси корректные аргументы. `slug=<...>` опционален.
- Если контекста недостаточно, вопросы формируются как `Вопрос N (Blocker|Clarification)` с `Зачем/Варианты/Default`; ответы — `Ответ N: ...`. После фиксации в PRD дублируй вопросы в `AIDD:OPEN_QUESTIONS` с `Q1/Q2/...`, чтобы их можно было ссылать из плана. Для research укажи подсказки в `## AIDD:RESEARCH_HINTS`.
- Если пользователь отвечает в чате — попроси прислать блок `AIDD:ANSWERS` с форматом `Answer N: ...` (номер совпадает с `Вопрос N`).
- Если ответы получены, но вопросы остаются в `AIDD:OPEN_QUESTIONS`, это неконсистентное состояние — синхронизируй их до `/feature-dev-aidd:review-spec`.

## Ожидаемый вывод
- Активный ticket/slug зафиксирован в `aidd/docs/.active_*`.
- `aidd/docs/prd/$1.prd.md` создан/обновлён (PENDING/BLOCKED до ответов).
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/feature-dev-aidd:idea-new ABC-123 slug=checkout-demo`
- `/feature-dev-aidd:idea-new ABC-123 Уточнить сценарий guest checkout для B2B`
