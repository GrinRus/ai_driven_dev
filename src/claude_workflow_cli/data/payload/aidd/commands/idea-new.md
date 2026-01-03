---
description: "Инициация фичи: setup ticket/slug → analyst → PRD draft + вопросы"
argument-hint: "<TICKET> [slug-hint] [note...]"
lang: ru
prompt_version: 1.2.7
source_version: 1.2.7
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_feature.py:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py:*)"
  - "Bash(claude-workflow analyst-check:*)"
  - "Bash(claude-workflow research:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
`/idea-new` фиксирует активный ticket/slug-hint, выставляет стадию `idea`, запускает саб-агента **analyst** и формирует PRD draft с вопросами. READY ставится только после ответов пользователя и актуального research. Свободный ввод после тикета используется как заметка для PRD.

## Входные артефакты
- `@aidd/docs/prd.template.md` — шаблон PRD (Status: draft, `## Диалог analyst`).
- `@aidd/docs/research/<ticket>.md`, `aidd/reports/research/*` — обновляются при необходимости.
- `aidd/docs/.active_ticket`, `aidd/docs/.active_feature` — активные маркеры.

## Когда запускать
- В начале работы над фичей, до плана/кода.
- Повторно — когда нужно обновить PRD и вопросы.

## Автоматические хуки и переменные
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_feature.py` синхронизирует `.active_*` и scaffold'ит PRD.
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py idea` фиксирует стадию `idea`.
- Команда должна запускать саб-агента **analyst** (Claude: Run agent → analyst).
- Аналитик инициирует `claude-workflow research --ticket <ticket> --auto` при нехватке контекста (если `--no-research` не задан).
- `claude-workflow analyst-check --ticket <ticket>` — проверка диалога/статуса после ответов.

## Что редактируется
- `aidd/docs/.active_ticket`, `aidd/docs/.active_feature`.
- `aidd/docs/prd/<ticket>.prd.md`.
- `aidd/docs/research/<ticket>.md` и `aidd/reports/research/*` (при необходимости).

## Пошаговый план
1. Зафиксируй стадию `idea`: `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py idea`.
2. Обнови активный тикет/slug: `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_feature.py "$1" [--slug-note "$2"]`.
3. Запусти саб-агента **analyst**; при нехватке контекста он инициирует research и обновляет PRD.
4. Верни список вопросов и статус PRD.

## Fail-fast и вопросы
- Нет тикета/slug — остановись и запроси корректные аргументы.
- Если контекста недостаточно, вопросы формируются как `Вопрос N (Blocker|Clarification)` с `Зачем/Варианты/Default`; ответы — `Ответ N: ...`.

## Ожидаемый вывод
- Активный ticket/slug зафиксирован в `aidd/docs/.active_*`.
- `aidd/docs/prd/<ticket>.prd.md` создан/обновлён (PENDING/BLOCKED до ответов).
- При необходимости обновлён `aidd/docs/research/<ticket>.md` и `aidd/reports/research/*`.
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/idea-new ABC-123 checkout-demo`
