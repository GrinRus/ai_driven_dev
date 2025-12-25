---
description: "Инициация фичи: аналитик + (опц.) auto-research → вопросы пользователю → PRD draft"
argument-hint: "<TICKET> [slug-hint] [note...]"
lang: ru
prompt_version: 1.2.2
source_version: 1.2.2
allowed-tools:
  - Read
  - Edit
  - Write
  - Grep
  - Glob
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_feature.py:*)"
  - "Bash(claude-workflow analyst:*)"
  - "Bash(claude-workflow analyst-check:*)"
  - "Bash(claude-workflow research:*)"
  - "Bash(rg:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
`/idea-new` — единый сценарий: фиксирует активный ticket, запускает аналитика, при нехватке контекста автоматически вызывает research, формирует PRD draft и список вопросов. READY ставится только после ответов пользователя и актуального research; команда завершается в состоянии PENDING/BLOCKED с вопросами для пользователя. Свободный ввод после тикета (и slug-hint) сохраняй как заметку в PRD.

## Входные артефакты
- Slug-hint пользователя (`[slug-hint]`, `rg <ticket> aidd/docs/**`) и свободные заметки (`[note...]`) — исходное описание и уточнения.
- @aidd/docs/prd.template.md — шаблон PRD (Status: draft, `## Диалог analyst`).
- `@aidd/docs/research/<ticket>.md`, `aidd/reports/research/*` — создаются/обновляются автоматически (если отчёта нет, разворачивается `aidd/docs/templates/research-summary.md` с baseline).
- Активные маркеры: `aidd/docs/.active_ticket`, `.active_feature`.

## Когда запускать
- В начале работы над фичей, до плана/кода.
- Повторно — только с `--force`, если нужно переинициализировать тикет/PRD: перечитай существующий PRD, не затирай ответы, добавь новые вопросы/источники и обнови статус/Researcher при изменении контекста.

## Автоматические хуки и переменные
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_feature.py` синхронизирует `aidd/docs/.active_*` (fallback на `aidd/docs`), scaffold'ит PRD.
- Внутри `/idea-new` автоматически запускается **analyst**; при нехватке контекста он инициирует `claude-workflow research --ticket <ticket> --auto [--paths ... --keywords ...]` (или просит пользователя, если задан `--no-research`).
- Флаги: `--auto-research` (по умолчанию on), `--no-research` — отключить автозапуск исследования.
- `claude-workflow analyst-check --ticket <ticket>` — валидация диалога/статусов после получения ответов.

## Что редактируется
- `aidd/docs/.active_ticket`, `.active_feature` — текущий тикет/slug.
- `aidd/docs/prd/<ticket>.prd.md` — основной документ (draft → READY/BLOCKED/PENDING).
- `aidd/docs/research/<ticket>.md` и `aidd/reports/research/*` — отчёт/контекст Researcher.
- Доп. заметки (`--note`) при необходимости.

## Пошаговый план
1. Запусти `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_feature.py "$1" [--slug-note "$2"]` — обновит `.active_*`, создаст PRD и, при отсутствии, research-заготовку (workflow живёт в ./aidd). Всё, что идёт после тикета/slug (`$ARGUMENTS`), зафиксируй как свободную заметку в PRD.
2. Автоматически запусти **analyst**: он читает slug-hint и артефакты, ищет контекст. При нехватке данных инициирует `claude-workflow research --ticket "$1" --auto [--paths ... --keywords ...]` (или просит пользователя при `--no-research`).
3. После research (если был) аналитик обновляет PRD, фиксирует источники и формирует блок «Вопросы к пользователю» в `## Диалог analyst`. READY не ставится, пока нет ответов и research не reviewed (кроме baseline-проектов); без ответов статус остаётся PENDING.
4. Заверши команду с явным списком вопросов/блокеров. Пользователь отвечает в формате `Ответ N: ...`; после ответов запусти `claude-workflow analyst-check --ticket "$1"` и, при необходимости, повторно аналитика для обновления статуса.

## Fail-fast и вопросы
- Нет тикета/slug — остановись и запроси корректные аргументы; не перезаписывай заполненный PRD без `--force`.
- Нет research или он устарел — аналитик инициирует research сам; при отключённом auto-research попроси пользователя запустить `/researcher`.
- Недостаточно данных после research — зафиксируй, что уже проверено (paths/keywords/rg), сформируй вопросы; READY не ставь до ответов (статус PENDING/BLOCKED).

## Ожидаемый вывод
- Активный ticket/slug зафиксирован в `aidd/docs/.active_*`.
- `aidd/docs/prd/<ticket>.prd.md` создан и заполнен (draft/PENDING/BLOCKED с вопросами; READY только после ответов).
- `aidd/docs/research/<ticket>.md` и `aidd/reports/research/*` актуализированы (или baseline).
- Пользователь получает список вопросов для перехода к READY/plan.

## Troubleshooting
- PRD остаётся draft/PENDING/BLOCKED: проверьте, что отвечены все `Вопрос N:` в `## Диалог analyst` и запустите `claude-workflow analyst-check --ticket <ticket>` (workflow живёт в ./aidd).
- Нет research или он pending: выполните `claude-workflow research --ticket <ticket> --auto` (либо `/researcher`), убедитесь в `Status: reviewed`.
- Команда ищет артефакты не там: запускайте из workspace, убедившись что `${CLAUDE_PLUGIN_ROOT:-./aidd}` указывает на каталог плагина; активные файлы должны лежать в `aidd/docs/.active_*`.

## Примеры CLI
- `/idea-new ABC-123 checkout-demo`
- `/idea-new ABC-123 --paths src/app:src/shared --keywords "payment,checkout" --slug-note checkout-demo`
- `!bash -lc 'claude-workflow research --ticket "ABC-123" --auto --note "reuse payment gateway"'`
