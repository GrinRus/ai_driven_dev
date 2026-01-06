---
description: "Инициация фичи: setup ticket/slug → analyst → PRD draft + вопросы"
argument-hint: "<TICKET> [slug-hint] [note...]"
lang: ru
prompt_version: 1.3.3
source_version: 1.3.3
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(claude-workflow set-active-feature:*)"
  - "Bash(claude-workflow set-active-stage:*)"
  - "Bash(claude-workflow analyst-check:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
`/idea-new` фиксирует активный ticket/slug-hint, выставляет стадию `idea`, запускает саб-агента **analyst** и формирует PRD draft с вопросами. Аналитик фиксирует контекст и заполняет `## Research Hints` в PRD. После ответов пользователя следующий обязательный шаг — `/researcher <ticket>`; READY ставится после ответов. Свободный ввод после тикета используется как заметка для PRD.

## Входные артефакты
- `@aidd/docs/prd/template.md` — шаблон PRD (Status: draft, `## Диалог analyst`).
- `@aidd/docs/research/<ticket>.md`, `aidd/reports/research/*` — если уже есть, использовать как контекст.
- `aidd/docs/.active_ticket`, `aidd/docs/.active_feature` — активные маркеры.

## Когда запускать
- В начале работы над фичей, до плана/кода.
- Повторно — когда нужно обновить PRD и вопросы.

## Автоматические хуки и переменные
- `claude-workflow set-active-feature` синхронизирует `.active_*` и scaffold'ит PRD.
- `claude-workflow set-active-stage idea` фиксирует стадию `idea`.
- Команда должна запускать саб-агента **analyst** (Claude: Run agent → analyst).
- `claude-workflow analyst-check --ticket <ticket>` — проверка диалога/статуса после ответов.

## Что редактируется
- `aidd/docs/.active_ticket`, `aidd/docs/.active_feature`.
- `aidd/docs/prd/<ticket>.prd.md`.

## Пошаговый план
1. Зафиксируй стадию `idea`: `claude-workflow set-active-stage idea`.
2. Обнови активный тикет/slug: `claude-workflow set-active-feature "$1" [--slug-note "$2"]`.
3. Запусти саб-агента **analyst**; он обновит PRD и заполнит блок `## Research Hints` (пути/ключевые слова/заметки).
4. Верни список вопросов и статус PRD; следующий шаг — `/researcher <ticket>`.

## Fail-fast и вопросы
- Нет тикета/slug — остановись и запроси корректные аргументы.
- Если контекста недостаточно, вопросы формируются как `Вопрос N (Blocker|Clarification)` с `Зачем/Варианты/Default`; ответы — `Ответ N: ...`. Для research укажи подсказки в `## Research Hints`.

## Ожидаемый вывод
- Активный ticket/slug зафиксирован в `aidd/docs/.active_*`.
- `aidd/docs/prd/<ticket>.prd.md` создан/обновлён (PENDING/BLOCKED до ответов).
- Ответ содержит `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## Примеры CLI
- `/idea-new ABC-123 checkout-demo`
