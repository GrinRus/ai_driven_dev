# AGENTS

Единая точка входа для агентов и команд AIDD.

## Базовые правила
- Все артефакты находятся в `aidd/**`.
- Канонический SDLC: см. `aidd/docs/sdlc-flow.md` и `aidd/docs/status-machine.md`.
- По умолчанию работаем по контракту: входные артефакты → выходные артефакты → статус.
- Ответ агента всегда начинается с `Checkbox updated:`.

## Что читать прежде всего
- `aidd/docs/sdlc-flow.md`
- `aidd/docs/status-machine.md`

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
