---
Ticket: <ABC-123>
Slug: <short-slug>
# Status: PENDING|READY|WARN|BLOCKED
Status: PENDING
Updated: <YYYY-MM-DD>
Owner: <name/team>
PRD: aidd/docs/prd/<ABC-123>.prd.md
Plan: aidd/docs/plan/<ABC-123>.md
Research: aidd/docs/research/<ABC-123>.md
ExpectedReports:
  tests: aidd/reports/tests/<ABC-123>/<scope_key>.jsonl
  review_report: aidd/reports/reviewer/<ABC-123>/<scope_key>.json
  reviewer_marker: aidd/reports/reviewer/<ABC-123>/<scope_key>.tests.json
  qa: aidd/reports/qa/<ABC-123>.json
---

# Tasklist: <ABC-123> — <short-slug>

> Единственный источник правды для implement/review/qa.
> Порядок чтения: `AIDD:CONTEXT_PACK` -> `AIDD:TEST_EXECUTION` -> `AIDD:ITERATIONS_FULL` -> `AIDD:NEXT_3`.

## AIDD:CONTEXT_PACK
Updated: <YYYY-MM-DD>
Ticket: <ABC-123>
Stage: <idea|research|plan|review-spec|review-plan|review-prd|tasklist|implement|review|qa|status>
Status: PENDING

### TL;DR
- Goal: <1 line>
- Current focus: <one item from AIDD:NEXT_3>
- Risks: <low|medium|high> — <why>

### Boundaries
- Allowed paths:
  - <path1/>
- Forbidden paths:
  - <pathX/> — <why>

### Defaults
- Feature flag: <none|flag>
- Contract/API: <short note or ref>
- Observability: <short note>

### References
- PRD: `aidd/docs/prd/<ABC-123>.prd.md`
- Research: `aidd/docs/research/<ABC-123>.md`
- Plan: `aidd/docs/plan/<ABC-123>.md`

## AIDD:TEST_STRATEGY
- Unit: <scope>
- Integration: <scope>
- Contract: <scope>
- E2E/Stand: <critical paths>
- Test data: <fixtures/mocks>

---

## AIDD:TEST_EXECUTION
- profile: <fast|targeted|full|none>
- tasks: <команды/таски>
- filters: <фильтры>
- when: <on_stop|checkpoint|manual>
- reason: <почему такой профиль>

---

## AIDD:ITERATIONS_FULL
- [ ] I1: <краткое название> (iteration_id: I1)
  - parent_iteration_id: none
  - Goal: <что именно делаем>
  - Outputs: <artifacts>
  - DoD: <done criteria>
  - Boundaries: <paths/modules>
  - Priority: medium
  - Blocking: false
  - deps: []
  - locks: []
  - Expected paths:
    - <path>
  - Commands:
    - <command or doc ref>
  - Steps:
    - <step 1>
    - <step 2>
  - Tests:
    - profile: none
    - tasks: []
    - filters: []
  - Acceptance mapping: <PRD refs>
  - Risks & mitigations: <risk -> mitigation>
- [ ] I2: <next bounded iteration> (iteration_id: I2)
  - parent_iteration_id: I1
  - Goal: <goal>
  - Outputs: <artifacts>
  - DoD: <done criteria>
  - Boundaries: <paths/modules>
  - Priority: medium
  - Blocking: false
  - deps: []
  - locks: []
  - Expected paths:
    - <path>
  - Commands:
    - <command or doc ref>
  - Steps:
    - <step 1>
  - Tests:
    - profile: none
    - tasks: []
    - filters: []
  - Acceptance mapping: <PRD refs>
  - Risks & mitigations: <risk -> mitigation>

---

## AIDD:NEXT_3
- [ ] I1: <кратко о текущем шаге> (ref: iteration_id=I1)
- [ ] I2: <следующий шаг> (ref: iteration_id=I2)

---

## AIDD:HANDOFF_INBOX
> Канонический формат handoff item:
> `- [ ] <title> (id: review:F6) (Priority: high) (Blocking: true)`
> Минимум полей под item: `source`, `Report`, `Status`, `scope`, `DoD`, `Boundaries`, `Tests`, `Notes`.

<!-- handoff:manual start -->
<!-- handoff:manual end -->

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

---

## AIDD:PROGRESS_LOG
> Мини‑лог: фиксируй кратко, обновляй после каждой итерации.
> Формат записи:
> `- YYYY-MM-DD source=implement id=I4 kind=iteration hash=abc123 link=aidd/reports/tests/<ticket>/<scope_key>.jsonl msg=short-note`
> `- YYYY-MM-DD source=review id=review:F6 kind=handoff hash=def456 link=aidd/reports/reviewer/<ticket>/<scope_key>.json msg=blocked`
- (empty)

---

## AIDD:HOW_TO_UPDATE
- Правило итерации: **1 чекбокс** (или 2 тесно связанных) — затем Stop.
- Формат закрытия: `- [x] I1: <title> (iteration_id: I1) (link: <commit/pr|report>)` или `- [x] <handoff title> (id: review:F6) (link: <commit/pr|report>)`.
- После каждого `[x]` обновляй `AIDD:NEXT_3` и `AIDD:PROGRESS_LOG`.
- Если меняешь тестовый профиль/команды — обнови `AIDD:TEST_EXECUTION`.
- Логи/stacktrace не вставлять в tasklist — только ссылки на `aidd/reports/**`.
