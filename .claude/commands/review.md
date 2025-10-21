---
description: "Код-ревью и возврат замечаний в задачи"
argument-hint: "<slug>"
allowed-tools: Read,Edit,Write,Grep,Glob,Bash(git diff:*)
---
Вызови саб‑агента **reviewer** для ревью изменений по `$1`.
При критичных замечаниях — статус BLOCKED и вернуть задачу саб‑агенту implementer; иначе — внести рекомендации в `docs/tasklist/$1.md`.
Если reviewer просит прогнать тесты, отметь это командой `claude-workflow reviewer-tests --status required [--feature $1]`, а после прогона обнови статус на `optional`.
Для формирования релизных заметок запусти пресет `feature-release` (обновляет `docs/release-notes.md` и фиксирует метрики).
