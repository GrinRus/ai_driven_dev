---
description: "План реализации по согласованному PRD + валидация"
argument-hint: "<TICKET>"
allowed-tools: Read,Edit,Write,Grep,Glob
---
1) Вызови саб‑агента **planner** для создания `docs/plan/$1.md` на основе `docs/prd/$1.prd.md`.
2) Проверь, что в PRD заполнен раздел `## PRD Review` и статус `Status: approved`. Если нет — остановись и запусти `/review-prd $1` (ticket).
3) Затем вызови саб‑агента **validator**. Если статус BLOCKED — верни список вопросов пользователю.
4) Обнови раздел «Открытые вопросы» в PRD/плане и перенеси action items из PRD Review в план.
5) При старте итерации можно развернуть пресет `feature-plan` (см. `claude-presets/feature-plan.yaml`) — он подставит задачи из backlog Wave 7 и цели демо.
