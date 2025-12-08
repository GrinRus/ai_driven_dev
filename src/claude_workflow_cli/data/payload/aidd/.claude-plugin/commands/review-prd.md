---
description: "Ревью PRD и фиксация статуса готовности"
argument-hint: "<TICKET>"
lang: ru
prompt_version: 1.0.0
source_version: 1.0.0
allowed-tools:
  - Read
  - Edit
  - Write
  - Grep
  - Glob
  - "Bash(python3 scripts/prd-review-agent.py:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/review-prd` запускает структурное ревью PRD перед планированием и реализацией. Она вызывает саб-агента `prd-reviewer`, обновляет раздел `## PRD Review` и фиксирует отчёт (`reports/prd/<ticket>.json`).

## Входные артефакты
- `docs/prd/<ticket>.prd.md` — основной документ.
- `docs/plan/<ticket>.md` (если есть) и ADR.
- `docs/research/<ticket>.md`, `doc/backlog.md` — контекст.

## Когда запускать
- После `/idea-new` и обновления PRD, перед `/plan-new`.
- Повторять при любых существенных изменениях PRD.

## Автоматические хуки и переменные
- `gate-workflow` требует `## PRD Review` со статусом `approved` (или явным разрешением) перед изменениями в `src/**`.
- Скрипт `python3 scripts/prd-review-agent.py --ticket <ticket> --report reports/prd/<ticket>.json --emit-text` сохраняет отчёт.

## Что редактируется
- `docs/prd/<ticket>.prd.md` — раздел `## PRD Review`.
- `docs/tasklist/<ticket>.md` — перенос блокирующих action items.
- `reports/prd/<ticket>.json` — структурированный вывод (генерируется скриптом).

## Пошаговый план
1. Подготовь контекст: открой PRD, план, ADR, заметки.
2. Вызови саб-агента **prd-reviewer** (через команду или палитру) и передай список рисков/критериев, которые нужно проверить.
3. Обнови `## PRD Review`: статус (approved/blocked/pending), summary, findings (critical/major/minor) и action items (чеклист с владельцами/сроками).
4. Перенеси блокирующие action items в `docs/tasklist/<ticket>.md` (укажи владельцев и сроки).
5. Зафиксируй результат в отчёте:
   ```
   !bash -lc 'python3 scripts/prd-review-agent.py --ticket "$1" --report "reports/prd/$1.json" --emit-text'
   ```

## Fail-fast и вопросы
- Если PRD не заполнен (Status: draft) или отсутствует — попроси аналитика завершить `/idea-new`.
- При отсутствии ADR/плана, на которые ссылается PRD, уточни у пользователя.
- Если выявлены blocker issues — остановись и верни задачу на доработку.

## Ожидаемый вывод
- Раздел `## PRD Review` обновлён, статус выставлен, findings/action items перечислены.
- `reports/prd/<ticket>.json` содержит тот же вывод.
- Блокирующие action items перенесены в tasklist.

## Примеры CLI
- `/review-prd ABC-123`
- `!bash -lc 'python3 scripts/prd-review-agent.py --ticket "ABC-123" --report "reports/prd/ABC-123.json" --emit-text'`
