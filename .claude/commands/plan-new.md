---
description: "План реализации по согласованному PRD + валидация"
argument-hint: "<slug>"
allowed-tools: Read,Edit,Write,Grep,Glob
---
1) Вызови саб‑агента **planner** для создания `docs/plan/$1.md` на основе `docs/prd/$1.prd.md`.
2) Затем вызови саб‑агента **validator**. Если статус BLOCKED — верни список вопросов пользователю.
3) Обнови раздел «Открытые вопросы» в PRD/плане.
