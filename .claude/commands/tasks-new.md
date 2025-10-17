---
description: "Сформировать чеклист задач (tasklist.md) для фичи"
argument-hint: "<slug>"
allowed-tools: Read,Edit,Write,Grep,Glob
---
На основе `docs/plan/$1.md` обнови @tasklist.md: добавь задачи с чекбоксами по шагам плана
(реализация, тесты, документация, ревью), отметь зависимости и критерии приёмки.
Перенеси все action items из раздела `## PRD Review` (статус approved) в отдельные чекбоксы.
При необходимости разверни пресет `feature-impl` — он создаёт блок `## $1` в `tasklist.md` с задачами Wave 7.
