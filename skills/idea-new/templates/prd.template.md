# PRD

Status: draft
Ticket: <ticket>
Updated: YYYY-MM-DD

## Диалог analyst
Ссылка на исследование: `aidd/docs/research/<ticket>.md`

Вопрос 1 (Blocker|Clarification): `<что уточнить>`
Зачем: `<что блокирует>`
Варианты: `A) ... B) ...`
Default: `<разумное значение по умолчанию>`

## AIDD:ANSWERS
> Только compact формат: `Q<N>=<token>` или `Q<N>="короткий текст"`.
`AIDD:ANSWERS Q1=A`

## AIDD:RESEARCH_HINTS
- **Paths**: `<path1:path2>`
- **Keywords**: `<kw1,kw2>`
- **Notes**: `<что проверить>`

## AIDD:CONTEXT_PACK
- `<краткий контекст>`

## AIDD:NON_NEGOTIABLES
- `<что нельзя нарушать>`

## AIDD:OPEN_QUESTIONS
- `Q1 -> <owner> -> <deadline>` or `none`

## AIDD:RISKS
- `<risk> -> <mitigation>`

## AIDD:DECISIONS
- `<decision> -> <why>`

## AIDD:GOALS
- `<goal>`

## AIDD:NON_GOALS
- `<non-goal>`

## AIDD:ACCEPTANCE
- `<AC-1>`
- `<AC-2>`

## AIDD:METRICS
- `<metric> -> <target>`

## AIDD:ROLL_OUT
- `<flags, rollout, rollback>`

## Summary
- **Feature**: `<name>`
- **Problem**: `<current pain or opportunity>`
- **Users / scope**: `<who is affected>`
- **Key dependencies**: `<services, teams, constraints>`

## Scenarios
1. `<primary user flow>`
2. `<edge case or failure flow>`

## Requirements
- Functional: `<required behavior>`
- Non-functional: `<performance, security, reliability>`

## PRD Review
Status: PENDING

### Verdict
- `<short verdict>`

### Findings
- `<severity> <issue> -> <recommendation>` or `None`

### Action items
- `<action> -> <owner> -> <deadline>` or `None`
