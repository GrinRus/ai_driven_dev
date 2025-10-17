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
!`python3 -c 'import pathlib, sys; target_dir = pathlib.Path("docs"); target_dir.mkdir(parents=True, exist_ok=True); (target_dir / ".active_feature").write_text(sys.argv[1], encoding="utf-8"); print(f"active feature: {sys.argv[1]}")' "$1"`
