# Anchor: implement

## Цели
- Закрыть 1 чекбокс (или 2 тесно связанных) за итерацию.
- Обновить `AIDD:CONTEXT_PACK` и прогресс в tasklist.

## MUST READ FIRST
- `aidd/docs/tasklist/<ticket>.md`: `AIDD:CONTEXT_PACK` + `Next 3`.
- `aidd/docs/plan/<ticket>.md`: границы итерации.
- `aidd/reports/context/latest_working_set.md` (если есть).

## MUST UPDATE
- `aidd/docs/tasklist/<ticket>.md`: `AIDD:CONTEXT_PACK`, чекбоксы, прогресс.
- `aidd/.cache/test-policy.env` (если задаёшь профиль).

## MUST NOT
- Выходить за рамки плана без обновления plan/tasklist.
- Делать промежуточные Stop до завершения итерации.

## Stop etiquette
- Собери микро‑правки в один батч → один Stop после DoD.

## Test defaults
- SubagentStop: default `fast`.
- Stop: default `targeted`.
- Явный policy имеет приоритет.
