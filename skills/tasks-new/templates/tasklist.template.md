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
> Всегда начинайте чтение с `## AIDD:CONTEXT_PACK`, затем `## AIDD:TEST_EXECUTION`, затем `## AIDD:ITERATIONS_FULL`, затем `## AIDD:NEXT_3`.

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
- tasks:
  - <command>
- filters: []
- when: <on_stop|checkpoint|manual>
- reason: <why this profile>

---

## AIDD:ITERATIONS_FULL
- [ ] I1: <current bounded step> (iteration_id: I1)
  - iteration_id: I1
  - State: open
  - parent_iteration_id: none
  - Goal: <what changes now>
  - Outputs: <artifacts>
  - DoD: <done criteria>
  - Boundaries: <paths/modules>
  - Priority: medium
  - deps: []
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
- [ ] I2: <next bounded step> (iteration_id: I2)
  - iteration_id: I2
  - State: open
  - parent_iteration_id: I1
  - Goal: <goal>
  - Outputs: <artifacts>
  - DoD: <done criteria>
  - Boundaries: <paths/modules>
  - Priority: medium
  - deps: []
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

---

## AIDD:NEXT_3
- [ ] I1: <current step> (ref: iteration_id=I1)
- [ ] I2: <next step> (ref: iteration_id=I2)

---

## AIDD:HANDOFF_INBOX
> Canonical handoff format:
> `- [ ] <title> (id: review:F6) (Priority: high) (Blocking: true)`
> Short example for a closed handoff:
> `- [x] <title> (id: review:F6) (Priority: high) (Blocking: true)`
> - source: review
> - Report: aidd/reports/<owner>/<ticket>/<scope_key>.json
> - Status: done
> - scope: iteration_id|n/a
> - DoD: <verification target>
> - Notes: <tradeoffs/risks>

<!-- handoff:manual start -->
<!-- handoff:manual end -->

---

## AIDD:QA_TRACEABILITY
- AC-1 -> <check> -> <met|not-met|not-verified> -> <evidence/link>
- AC-2 -> <check> -> <met|not-met|not-verified> -> <evidence/link>

---

## AIDD:CHECKLIST
### AIDD:CHECKLIST_QA
- [ ] QA: <critical acceptance check>

---

## AIDD:PROGRESS_LOG
> Формат записи:
> `- YYYY-MM-DD source=implement id=I1 kind=iteration hash=abc123 link=aidd/reports/tests/<ticket>/<scope_key>.jsonl msg=short-note`
> `- YYYY-MM-DD source=review id=review:F6 kind=handoff hash=def456 link=aidd/reports/reviewer/<ticket>/<scope_key>.json msg=blocked`
- (empty)

---

## AIDD:HOW_TO_UPDATE
- Правило итерации: **1 чекбокс** (или 2 тесно связанных) — затем Stop.
- После каждого `[x]` обновляй `AIDD:NEXT_3` и добавляй запись в `AIDD:PROGRESS_LOG`.
- Если меняется тестовый профиль/команды — обнови `AIDD:TEST_EXECUTION`.
- Не вставляй raw logs в tasklist; оставляй ссылки на `aidd/reports/**`.
