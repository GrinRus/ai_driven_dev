---
description: "Код-ревью и возврат замечаний в задачи"
argument-hint: "<TICKET>"
allowed-tools: Read,Edit,Write,Grep,Glob,Bash(git diff:*),Bash(claude-workflow reviewer-tests:*),Bash(claude-workflow progress:*)
---
Вызови саб‑агента **reviewer** для ревью изменений по `$1`.
При критичных замечаниях — статус BLOCKED и вернуть задачу саб‑агенту implementer; иначе — внести рекомендации в `docs/tasklist/$1.md`, явно указывая, какие чекбоксы закрыты и какие остаются `- [ ]`.
После обновления tasklist запусти `!bash -lc 'claude-workflow progress --source review --ticket "$1"'`, чтобы убедиться, что прогресс зафиксирован.
В финальном ответе добавь строку `Checkbox updated: <перечисли закрытые/открытые чекбоксы>` и короткое резюме следующих шагов для команды.
Если reviewer просит прогнать тесты, отметь это командой `claude-workflow reviewer-tests --status required [--ticket $1]`, а после прогона обнови статус на `optional`.
Для формирования релизных заметок запусти пресет `feature-release` (обновляет `docs/release-notes.md` и фиксирует метрики).
