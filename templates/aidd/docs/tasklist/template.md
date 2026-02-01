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
  tests: aidd/reports/tests/<ABC-123>/<scope_key>.jsonl  # optional
  reviewer: aidd/reports/reviewer/<ABC-123>/<scope_key>.json # marker/summary
  qa: aidd/reports/qa/<ABC-123>.json
---

# Tasklist: <ABC-123> — <short-slug>

> Единственный источник правды для implement/review/qa.
> Всегда начинайте чтение с `## AIDD:CONTEXT_PACK`, затем `## AIDD:SPEC_PACK`, затем `## AIDD:TEST_EXECUTION`, затем `## AIDD:ITERATIONS_FULL`, затем `## AIDD:NEXT_3`.

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

### Blockers summary (handoff)
- <handoff-id> — <1 строка, почему блокирует>

### References
- Architecture Profile: aidd/docs/architecture/profile.md
- Spec: aidd/docs/spec/<ABC-123>.spec.yaml
- PRD: aidd/docs/prd/<ABC-123>.prd.md (ищи #AIDD:ACCEPTANCE, #AIDD:ROLL_OUT)
- Research: aidd/docs/research/<ABC-123>.md (ищи #AIDD:INTEGRATION_POINTS)
- Plan: aidd/docs/plan/<ABC-123>.md (ищи #AIDD:FILES_TOUCHED, #AIDD:ITERATIONS)
- Reports:
  - reviewer: aidd/reports/reviewer/<ABC-123>/<scope_key>.json
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

## AIDD:TEST_EXECUTION
> Конкретные команды/фильтры запуска (execution‑уровень).
- profile: <fast|targeted|full|none>
- tasks: <команды/таски>
- filters: <фильтры>
- when: <on_stop|checkpoint|manual>
- reason: <почему такой профиль>

---

## AIDD:ITERATIONS_FULL
> Полный список итераций реализации (от 1 до N). Должен быть **детальнее плана** и не оставлять пробелов.
> Канонический формат итерации: `- [ ] I7: <title> (iteration_id: I7)`
- [ ] I1: <краткое название> (iteration_id: I1)
  - parent_iteration_id: <I0|none>  # optional
  - Goal: <что именно делаем>
  - Outputs: <артефакты итерации>
  - DoD: <как проверить готовность>
  - Boundaries: <пути/модули + что не трогаем>
  - Priority: <low|medium|high>  # optional
  - Blocking: <true|false>       # optional
  - deps: [<I0>, <review:F1>]    # optional
  - locks: [<db-schema>]         # optional
  - Expected paths:
    - <path1/**>
    - <path2/**>
  - Size budget:
    - max_files: <N>
    - max_loc: <N>
  - Commands:
    - <doc/ref or command>
  - Exit criteria:
    - <критерий 1>
    - <критерий 2>
  - Steps:
    - <шаг 1>
    - <шаг 2>
    - <шаг 3>
  - Tests:
    - profile: <fast|targeted|full|none>
    - tasks: <команды/таски>
    - filters: <фильтры>
  - Acceptance mapping: <AC-1, spec:...>
  - Risks & mitigations: <риск → митигация>
  - Dependencies: <сервисы/фичефлаги/данные>
- [ ] I2: <...> (iteration_id: I2)
  - parent_iteration_id: <I1|none>  # optional
  - Goal: <...>
  - Outputs: <...>
  - DoD: <...>
  - Boundaries: <...>
  - Priority: <low|medium|high>  # optional
  - Blocking: <true|false>       # optional
  - deps: [<I0>, <review:F1>]    # optional
  - locks: [<db-schema>]         # optional
  - Expected paths:
    - <path1/**>
  - Size budget:
    - max_files: <N>
    - max_loc: <N>
  - Commands:
    - <doc/ref or command>
  - Exit criteria:
    - <...>
  - Steps:
    - <...>
  - Tests:
    - profile: <fast|targeted|full|none>
    - tasks: <...>
    - filters: <...>
  - Acceptance mapping: <...>
  - Risks & mitigations: <...>
  - Dependencies: <...>
- [ ] I3..N: <...>

---

## AIDD:NEXT_3
> 3 ближайших implement‑чекбокса. Pointer list: 1–2 строки и `ref:` на детализацию.
- [ ] I1: <кратко о текущем шаге> (ref: iteration_id=I1)
- [ ] review:F6: <blocking handoff> (ref: id=review:F6)
- [ ] (none)

---

## AIDD:OUT_OF_SCOPE_BACKLOG
> Побочные идеи/задачи, которые НЕ входят в текущий work_item (без расширения scope).
- [ ] <идея/задача> (source: implement|review|qa|research|manual)

---

## AIDD:HANDOFF_INBOX
> Сюда падают задачи из Research/Review/QA (с source: aidd/reports/...).
> Формат задачи (обязательно):
> Канонический формат: `- [ ] <title> (id: review:F6) (Priority: high) (Blocking: true)`
> Source blocks вставляются задачей derive (`<!-- handoff:<source> start --> ... <!-- end -->`).
> Ручные задачи храните в `handoff:manual` — derive/normalize их не трогают.
- [ ] <title> (id: review:F6) (Priority: high) (Blocking: true)
  - source: review|qa|research|manual
  - Report: <aidd/reports/...>
  - Status: open|done|blocked
  - scope: iteration_id|n/a
  - DoD: <как проверить, что исправлено>
  - Boundaries:
    - must-touch: ["path1", "path2"]
    - must-not-touch: ["pathX"]
  - Tests:
    - profile: fast|targeted|full|none
    - tasks: ["..."]
    - filters: ["..."]
  - Notes: <tradeoffs/риски/почему важно>

> Примеры:
<!-- handoff:manual start -->
<!-- handoff:manual end -->

> Примеры:
- [ ] Critical null check in webhook handler (id: review:null-check) (Priority: high) (Blocking: true)
  - source: review
  - Report: aidd/reports/reviewer/<ticket>/<scope_key>.json
  - Status: open
  - scope: I2
  - DoD: webhook rejects empty payload with 4xx + unit test updated
  - Boundaries:
    - must-touch: ["src/webhooks/", "tests/webhooks/"]
    - must-not-touch: ["infra/"]
  - Tests:
    - profile: targeted
    - tasks: ["pytest tests/webhooks/test_handler.py"]
    - filters: []
  - Notes: prevents silent 500 on missing payload
- [ ] AC-3 export fails on empty data (id: qa:export-empty) (Priority: high) (Blocking: true)
  - source: qa
  - Report: aidd/reports/qa/<ticket>.json
  - Status: open
  - scope: n/a
  - DoD: export returns empty CSV with headers + QA traceability updated
  - Boundaries:
    - must-touch: ["src/export/"]
    - must-not-touch: ["db/migrations/"]
  - Tests:
    - profile: fast
    - tasks: []
    - filters: []
  - Notes: blocks release for AC-3

---

## AIDD:QA_TRACEABILITY
> AC → check → result → evidence.
- AC-1 → <check> → <met|not-met|not-verified> → <evidence/link>
- AC-2 → <check> → <met|not-met|not-verified> → <evidence/link>

---

## AIDD:CHECKLIST

### AIDD:CHECKLIST_SPEC
- [ ] PRD: Status READY (и нет незакрытых blocker вопросов)
- [ ] Research: Status reviewed
- [ ] Plan: существует и валиден
- [ ] Review Spec: Plan Review READY + PRD Review READY
- [ ] Spec interview (optional): spec обновлён; затем `/feature-dev-aidd:tasks-new` для синхронизации tasklist

### AIDD:CHECKLIST_IMPLEMENT
- [ ] Реализован функционал для checkbox #1 из AIDD:NEXT_3
- [ ] Добавлены/обновлены тесты по плану
- [ ] Обновлён AIDD:CONTEXT_PACK (scope + test policy)
- [ ] Обновлён AIDD:TEST_EXECUTION (если менялась тестовая тактика)
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
> `- YYYY-MM-DD source=implement id=I4 kind=iteration hash=abc123 link=aidd/reports/tests/<ticket>/<scope_key>.jsonl msg=short-note`
> `- YYYY-MM-DD source=review id=review:F6 kind=handoff hash=def456 link=aidd/reports/reviewer/<ticket>/<scope_key>.json msg=blocked`
- YYYY-MM-DD source=implement id=I1 kind=iteration hash=abc123 link=aidd/reports/tests/<ticket>/<scope_key>.jsonl msg=...

---

## AIDD:HOW_TO_UPDATE
- Правило итерации: **1 чекбокс** (или 2 тесно связанных) — затем Stop.
- Отмечайте чекбоксы так:
  - `- [x] I1: <title> (iteration_id: I1) (link: <commit/pr|report>)`
  - `- [x] <handoff title> (id: review:F6) (link: <commit/pr|report>)`
- После каждого [x] обновляй `AIDD:NEXT_3` (pointer list) и добавляй запись в `AIDD:PROGRESS_LOG`.
- Если меняешь тестовый профиль/команды — обнови `AIDD:TEST_EXECUTION`.
- Если обновили spec — запусти `/feature-dev-aidd:tasks-new` для синхронизации tasklist.
- Логи/stacktrace не вставлять в tasklist — только ссылки на `aidd/reports/**`.
