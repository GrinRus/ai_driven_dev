# Anchor: implement

## Goals
- Закрыть 1 чекбокс (или 2 тесно связанных) за итерацию.
- Обновить AIDD:CONTEXT_PACK и прогресс в tasklist.
- Минимизировать Stop → минимизировать лишние тесты.

## Graph Read Policy
- MUST: читать `aidd/reports/research/<ticket>-call-graph.pack.*` или `graph-slice` pack.
- MUST: точечный `rg` по `aidd/reports/research/<ticket>-call-graph.edges.jsonl`.
- MUST NOT: `Read` full `*-call-graph-full.json` или `*.cjson`.

## MUST READ FIRST
- aidd/docs/tasklist/<ticket>.md: AIDD:CONTEXT_PACK + AIDD:TEST_EXECUTION + AIDD:NEXT_3
- aidd/docs/plan/<ticket>.md: границы итерации (DoD)
- aidd/docs/spec/<ticket>.spec.yaml: contracts, risks, test strategy (if exists)
- aidd/reports/context/latest_working_set.md (если есть)

## MUST UPDATE
- aidd/docs/tasklist/<ticket>.md: чекбоксы + AIDD:CONTEXT_PACK + AIDD:PROGRESS_LOG
- aidd/.cache/test-policy.env (если задаёшь профиль явно)

## MUST NOT
- Выходить за рамки плана без обновления plan/tasklist.
- Делать промежуточные Stop до завершения итерации.

## Stop etiquette
- Собери микро‑правки в один батч → один Stop после DoD.

## Test defaults
- Default profile: fast (если не задан policy)
- targeted/full/none — только явно через policy.
