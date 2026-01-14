---
Ticket: <ABC-123>
Slug: <short-slug>
Status: PENDING   # PENDING|READY|WARN|BLOCKED
Updated: <YYYY-MM-DD>
Owner: <name/team>
PRD: aidd/docs/prd/<ABC-123>.prd.md
Plan: aidd/docs/plan/<ABC-123>.md
Research: aidd/docs/research/<ABC-123>.md
Spec: aidd/docs/spec/<ABC-123>.spec.yaml
Reports:
  tests: aidd/reports/tests/<ABC-123>.*          # optional
  reviewer: aidd/reports/reviewer/<ABC-123>.json # marker/summary
  qa: aidd/reports/qa/<ABC-123>.json
---

# Tasklist: <ABC-123> — <short-slug>

> Единственный источник правды для implement/review/qa.
> Всегда начинайте чтение с `## AIDD:CONTEXT_PACK`, затем `## AIDD:SPEC_PACK`, затем `## AIDD:ITERATIONS_FULL`, затем `## AIDD:NEXT_3`.

## AIDD:CONTEXT_PACK
Updated: <YYYY-MM-DD>
Ticket: <ABC-123>
Stage: <idea|research|plan|review-plan|review-prd|spec-interview|tasklist|implement|review|qa|release>
Status: <PENDING|READY|WARN|BLOCKED>

### TL;DR
- Goal: <1–2 строки — что делаем>
- Current focus (1 checkbox): <точное имя из AIDD:NEXT_3>
- Done since last pack: <1–3 пункта, кратко>
- Risk level: <low|medium|high> — <почему 1 строка>

### Scope & boundaries
- Allowed paths (patch boundaries):
  - <path1/>
  - <path2/>
- Forbidden / out-of-scope:
  - <pathX/> — <почему>
- Integrations / dependencies:
  - <api/service/db/topic> — <что важно>

### Decisions & defaults (living)
- Feature flag: <none|flag_name + default>
- Contract/API: <ссылка на spec или 1 строка>
- Data model changes: <none|migrations needed: ...>
- Observability: <logs/metrics/tracing expectations>

### Test policy (iteration budget)
- Cadence: <on_stop|checkpoint|manual>
- Profile: <fast|targeted|full|none>
- Tasks: <пример: :module:test или npm test ...> (если targeted/full)
- Filters: <если применимо>
- Budget minutes: <N>
- Known flaky / failing: <none|link to aidd/reports/tests/...>

### Commands quickstart (copy/paste)
- Format: <hook does it|cmd>
- Tests (manual): <cmd for targeted/full>
- Run/Dev: <cmd / url / emulator / device steps> (optional)

### Open questions / blockers
- Q1: <...>
- Q2: <...>

### References
- Spec: aidd/docs/spec/<ABC-123>.spec.yaml
- PRD: aidd/docs/prd/<ABC-123>.prd.md (ищи #AIDD:ACCEPTANCE, #AIDD:ROLL_OUT)
- Research: aidd/docs/research/<ABC-123>.md (ищи #AIDD:INTEGRATION_POINTS)
- Plan: aidd/docs/plan/<ABC-123>.md (ищи #AIDD:FILES_TOUCHED, #AIDD:ITERATIONS)
- Reports:
  - reviewer: aidd/reports/reviewer/<ABC-123>.json
  - qa: aidd/reports/qa/<ABC-123>.json

---

## AIDD:SPEC_PACK
Updated: <YYYY-MM-DD>
Spec: aidd/docs/spec/<ABC-123>.spec.yaml (status: <draft|ready>|none)
- Goal: <1–2 строки>
- Non-goals:
  - <...>
- Key decisions:
  - <...>
- Risks:
  - <...>

## AIDD:TEST_STRATEGY
- Unit: <scope>
- Integration: <scope>
- Contract: <scope>
- E2E/Stand: <critical paths>
- Test data: <fixtures/mocks>

---

## AIDD:ITERATIONS_FULL
> Полный список итераций реализации (от 1 до N). Должен быть **детальнее плана** и не оставлять пробелов.
- Iteration 1: <краткое название>
  - Goal: <что именно делаем>
  - DoD: <как проверить готовность>
  - Boundaries: <пути/модули + что не трогаем>
  - Tests:
    - profile: <fast|targeted|full|none>
    - tasks: <команды/таски>
    - filters: <фильтры>
  - Dependencies: <сервисы/фичефлаги/данные>
  - Risks: <что может пойти не так>
- Iteration 2: <...>
  - Goal: <...>
  - DoD: <...>
  - Boundaries: <...>
  - Tests:
    - profile: <fast|targeted|full|none>
    - tasks: <...>
    - filters: <...>
  - Dependencies: <...>
  - Risks: <...>
- Iteration 3..N: <...>

---

## AIDD:NEXT_3
> 3 ближайших implement‑чекбокса (каждый с DoD/Boundaries/Tests). Регулярно обновляй после каждой итерации.
- [ ] <1. ближайший чекбокс (одна итерация)>
  - DoD: <что считается готовым>
  - Boundaries: <пути/модули + что не трогаем>
  - Tests:
    - profile: <fast|targeted|full|none>
    - tasks: <команды/таски>
    - filters: <фильтры>
  - Notes: <важные нюансы>
- [ ] <2. следующий>
  - DoD: <...>
  - Boundaries: <...>
  - Tests:
    - profile: <fast|targeted|full|none>
    - tasks: <...>
    - filters: <...>
  - Notes: <...>
- [ ] <3. третий>
  - DoD: <...>
  - Boundaries: <...>
  - Tests:
    - profile: <fast|targeted|full|none>
    - tasks: <...>
    - filters: <...>
  - Notes: <...>

---

## AIDD:HANDOFF_INBOX
> Сюда падают задачи из Research/Review/QA (с source: aidd/reports/...).
- [ ] Research: <title> — <recommendation> (source: aidd/reports/research/<ABC-123>-context.json)
- [ ] Review: <severity> <title> — <recommendation> (source: aidd/reports/reviewer/<ABC-123>.json)
- [ ] QA: <severity> <title> — <recommendation> (source: aidd/reports/qa/<ABC-123>.json)

---

## AIDD:CHECKLIST

### AIDD:CHECKLIST_SPEC
- [ ] PRD: Status READY (и нет незакрытых blocker вопросов)
- [ ] Research: Status reviewed
- [ ] Plan: существует и валиден
- [ ] Review Spec: Plan Review READY + PRD Review READY
- [ ] Spec interview (optional): spec обновлён; затем `/tasks-new` для синхронизации tasklist

### AIDD:CHECKLIST_IMPLEMENT
- [ ] Реализован функционал для checkbox #1 из AIDD:NEXT_3
- [ ] Добавлены/обновлены тесты по плану
- [ ] Обновлён AIDD:CONTEXT_PACK (scope + test policy)
- [ ] Прогресс отмечен (см. AIDD:PROGRESS_LOG)

### AIDD:CHECKLIST_REVIEW
- [ ] Reviewer: замечания добавлены в tasklist (handoff)
- [ ] Требуемость тестов выставлена (если используете reviewer marker)
- [ ] Изменения соответствуют plan/PRD (нет лишнего)

### AIDD:CHECKLIST_QA
- [ ] QA: AIDD:ACCEPTANCE проверены (traceability)
- [ ] QA report сохранён (aidd/reports/qa/<ticket>.json)
- [ ] Known issues задокументированы

### AIDD:CHECKLIST_RELEASE
- [ ] Release notes / changelog (если нужно)
- [ ] Deploy на стенд (env + версия + время)
- [ ] Smoke / e2e (если есть)
- [ ] Мониторинг/алерты/дашборды проверены

### AIDD:CHECKLIST_POST_RELEASE
- [ ] Rollback plan проверен (если релевантно)
- [ ] Метрики успеха/guardrails собраны
- [ ] Техдолг/следующие шаги заведены

---

## AIDD:PROGRESS_LOG
> Мини‑лог: фиксируй кратко, обновляй после каждой итерации.
> Формат записи:
> `- YYYY-MM-DD Iteration N: <что сделано> (checkbox: <...>) (tests: <...>) (artifacts: <...>)`
- <YYYY-MM-DD> Iteration 1: ...

---

## AIDD:HOW_TO_UPDATE
- Правило итерации: **1 чекбокс** (или 2 тесно связанных) — затем Stop.
- Отмечайте чекбоксы так:
  - `- [x] <описание> — YYYY-MM-DD (iteration N) (tests: fast|targeted|full|none) (link: <commit/pr>)`
- После каждой итерации обновляй `AIDD:NEXT_3` и `AIDD:PROGRESS_LOG`.
- Если обновили spec — запусти `/tasks-new` для синхронизации tasklist.
- Логи/stacktrace не вставлять в tasklist — только ссылки на `aidd/reports/**`.
