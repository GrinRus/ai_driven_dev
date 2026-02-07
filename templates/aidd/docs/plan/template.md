# План реализации — шаблон

Status: PENDING
PRD: `aidd/docs/prd/<ticket>.prd.md`
Research: `aidd/docs/research/<ticket>.md`

## AIDD:CONTEXT_PACK
- `<краткий контекст итерации>`

## AIDD:NON_NEGOTIABLES
- `<что нельзя нарушать>`

## AIDD:OPEN_QUESTIONS
- `PRD Q1 → <кто отвечает> → <срок>`
- `<новый вопрос> → <кто отвечает> → <срок>`
> Если вопрос уже есть в PRD `AIDD:OPEN_QUESTIONS`, не повторяй текст — укажи ссылку `PRD QN`.

## AIDD:ANSWERS
> Единый формат ответов из чата (если вопросы были).
- Answer 1: <ответ>
- Answer 2: <ответ>

## AIDD:RISKS
- `<риск> → <митигация>`

## AIDD:DECISIONS
- `<решение> → <почему>`

## AIDD:DESIGN
- `<ключевые слои/границы>`

## AIDD:FILES_TOUCHED
- `<путь/модуль> — <что меняем>`

## AIDD:ITERATIONS
- iteration_id: I1
  - Goal: <цель итерации>
  - Boundaries: <модули/границы>
  - Outputs: <артефакты>
  - DoD: <критерий готовности>
  - Test categories: <unit|integration|e2e>

## AIDD:TEST_STRATEGY
- `<что/где/как тестируем>`

## 1. Контекст и цели
- **Цель:** [кратко]
- **Scope:** [что в/что вне]
- **Ограничения:** [тех/процессные]

## 2. Дизайн и паттерны
- **Слои/границы:** [domain/app/infra]
- **Паттерны:** [service layer / ports-adapters / другое]
- **Reuse-точки:** [что используем]

## 3. Files & Modules Touched
- [путь/модуль] — [что меняем]

## 4. Итерации и DoD
### Итерация I1
- Goal: [что именно делаем]
- Boundaries: [модули/пути, где меняем]
- Outputs: [артефакты итерации]
- DoD: [критерии готовности]
- Test categories: [unit/integration/e2e]

### Итерация I2
- ...

## 5. Test Strategy
- По итерациям: [что/где тестируем]
- Категории: [unit/integration/e2e]

## 6. Feature Flags & Migrations
- Флаги: [название/поведение]
- Миграции: [что/где]

## 7. Observability
- Логи/метрики/алерты: [что добавляем]

## 8. Риски
- [риск] → [митигация]

## 9. Открытые вопросы
- [вопрос] → [ответственный] → [срок]

## Plan Review
Status: PENDING
Note: Action items must live under `### Action items`. Avoid checkboxes elsewhere in Plan Review.

### Summary
- [краткий вывод]

### Findings
- [severity] [проблема] — [рекомендация]

### Action items
- None
- <действие> — <ответственный> — <срок>
