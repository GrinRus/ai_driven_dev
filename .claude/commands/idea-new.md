---
description: "Инициация фичи: сбор идеи → уточнения → PRD"
argument-hint: "<slug> [TICKET]"
allowed-tools: Read,Edit,Write,Grep,Glob,Bash(*)
---
1) Установи активную фичу: создавай/перезапиши файл `docs/.active_feature` значением `$1` — это единственный способ синхронизировать slug (отдельной `/feature-activate` больше нет).
2) Используя @docs/prd.template.md, @conventions.md и @workflow.md, создай/обнови `docs/prd/$1.prd.md`.
3) Вызови саб‑агента **analyst** для итеративного уточнения идеи. Если передан TICKET ($2) — добавь раздел Tracking.
4) Для быстрого старта воспользуйся пресетом `feature-prd` (`bash init-claude-workflow.sh --preset feature-prd --feature "$1"`), чтобы подхватить готовый шаблон и цели из backlog/usage-demo.

Выполни:
- Если отсутствует `tools/set_active_feature.py`, создай его из шаблона (см. README) через инструмент `Write`.
- Запусти скрипт без редиректов:
!`python3 tools/set_active_feature.py "$1"`
