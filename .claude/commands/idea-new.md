---
description: "Инициация фичи: сбор идеи → уточнения → PRD"
argument-hint: "<slug> [TICKET]"
allowed-tools: Read,Edit,Write,Grep,Glob,Bash(*)
---
1) Установи активную фичу: создавай/перезапиши файл `docs/.active_feature` значением `$1`.
2) Используя @docs/prd.template.md, @conventions.md и @workflow.md, создай/обнови `docs/prd/$1.prd.md`.
3) Вызови саб‑агента **analyst** для итеративного уточнения идеи. Если передан TICKET ($2) — добавь раздел Tracking.

Выполни:
!`mkdir -p docs && printf "%s" "$1" > docs/.active_feature && echo "active feature: $1"`
