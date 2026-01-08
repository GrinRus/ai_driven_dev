# AGENTS

Единая точка входа для агентов и команд AIDD.

## Базовые правила
- Все артефакты находятся в `aidd/**`.
- Канонический SDLC: см. `aidd/docs/sdlc-flow.md` и `aidd/docs/status-machine.md`.
- По умолчанию работаем по контракту: входные артефакты → выходные артефакты → статус.
- Ответ агента всегда начинается с `Checkbox updated:`.

## MUST KNOW FIRST (read-once / read-if-changed)
- `aidd/AGENTS.md` — read-once; перечитывать только при изменениях workflow.
- `aidd/docs/sdlc-flow.md` — только при первом входе или при изменениях процесса.
- `aidd/docs/status-machine.md` — только при первом входе или при изменениях статусов.
- `aidd/reports/context/latest_working_set.md` — краткий рабочий контекст (если файл существует).
- `aidd/docs/anchors/<stage>.md` — stage‑anchor (если есть).
- `aidd/docs/tasklist/<ticket>.md` — сначала `AIDD:CONTEXT_PACK`, затем `Next 3`.

## Политика чтения
- Если рядом есть `*.pack.yaml` — читать pack; полный JSON только при need‑to‑know.
- Сначала искать/читать фрагменты (`rg` → `sed`); полный `Read` — крайний случай.

## Что нельзя делать
- Менять файлы вне согласованного плана/тасклиста.
- Продолжать работу без обязательных артефактов и статусов.
- Переопределять порядок стадий без обновления документации и гейтов.

## Артефакты и отчёты
- PRD: `aidd/docs/prd/<ticket>.prd.md`
- Research: `aidd/docs/research/<ticket>.md`
- Plan: `aidd/docs/plan/<ticket>.md`
- Tasklist: `aidd/docs/tasklist/<ticket>.md`
- Reports: `aidd/reports/**`

## Формат вопросов к пользователю
```
Вопрос N (Blocker|Clarification): ...
Зачем: ...
Варианты: A) ... B) ...
Default: ...
```
