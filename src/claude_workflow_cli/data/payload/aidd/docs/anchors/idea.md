# Anchor: idea

## Цели
- Зафиксировать ticket и создать PRD draft с вопросами.
- Заполнить базовые AIDD:* секции и Research Hints.

## MUST KNOW FIRST
- `aidd/AGENTS.md`.
- `aidd/docs/prd/template.md`.
- `aidd/docs/sdlc-flow.md` (read-once).
- `aidd/docs/status-machine.md` (read-once).

## Inputs
- Ввод пользователя (идея, ограничения, метрики).
- Существующие документы (backlog/ADR), если есть.

## Outputs/Contract
- `aidd/docs/prd/<ticket>.prd.md` со статусом `draft|PENDING|BLOCKED|READY`.
- Заполненные `AIDD:*` секции и блок `## Research Hints`.

## MUST UPDATE
- `aidd/docs/prd/<ticket>.prd.md`.
- `aidd/docs/.active_ticket` и `aidd/docs/.active_stage`.

## MUST NOT
- Переходить к планированию без `PRD READY`.
- Запускать research без фиксации Research Hints при тонком контексте.

## Blockers
- Не задан ticket.
- Нет ответов на ключевые вопросы пользователя.
