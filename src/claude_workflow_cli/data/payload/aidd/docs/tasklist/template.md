---
Ticket: <ABC-123>
Slug: <short-slug>
Status: PENDING   # PENDING|READY|WARN|BLOCKED
Updated: <YYYY-MM-DD>
Owner: <name/team>
PRD: aidd/docs/prd/<ABC-123>.prd.md
Plan: aidd/docs/plan/<ABC-123>.md
Research: aidd/docs/research/<ABC-123>.md
Reports:
  tests: aidd/reports/tests/<ABC-123>.*          # optional
  reviewer: aidd/reports/reviewer/<ABC-123>.json # marker/summary
  qa: aidd/reports/qa/<ABC-123>.json
---

# Tasklist: <ABC-123> — <short-slug>

> Единственный источник правды для implement/review/qa.
> Всегда начинайте чтение с `## AIDD:CONTEXT_PACK`, затем `## AIDD:SPEC_PACK`, затем `## AIDD:NEXT_3`.

## AIDD:CONTEXT_PACK
Updated: <YYYY-MM-DD>
Ticket: <ABC-123>
Stage: <idea|research|plan|review-plan|review-prd|tasklist|implement|review|qa|release>
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
- Contract/API: <ссылка на PRD якорь или 1 строка>
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
- PRD: aidd/docs/prd/<ABC-123>.prd.md (ищи #AIDD:ACCEPTANCE, #AIDD:ROLL_OUT)
- Research: aidd/docs/research/<ABC-123>.md (ищи #AIDD:INTEGRATION_POINTS)
- Plan: aidd/docs/plan/<ABC-123>.md (ищи #AIDD:FILES_TOUCHED, #AIDD:ITERATIONS)
- Reports:
  - reviewer: aidd/reports/reviewer/<ABC-123>.json
  - qa: aidd/reports/qa/<ABC-123>.json

---

## AIDD:SPEC
Status: DRAFT   # DRAFT|READY
Updated: <YYYY-MM-DD>
Owner: <name/team>
Source:
- plan: aidd/docs/plan/<ABC-123>.md
- prd: aidd/docs/prd/<ABC-123>.prd.md
- research: aidd/docs/research/<ABC-123>.md

## AIDD:SPEC_PACK
> Token-first YAML. Обновляй после каждого интервью-прохода и при смене решений.

```yaml
ticket: "<ABC-123>"
status: "DRAFT" # DRAFT|READY

surfaces: ["frontend","backend"]   # + "mobile" при необходимости

scope:
  in: []
  out: []

journeys:
  - id: "J1"
    title: ""
    actors: []
    happy_path: []
    failure_modes: []

ui:
  screens: []
  states:
    loading: true
    empty: true
    error: true
    partial_success: false
  a11y: []
  i18n: []
  analytics_events: []   # no PII

contracts:
  api: []      # {name, auth, request, response, errors, timeouts}
  events: []   # {topic, schema, compat, idempotency}

data_model:
  entities: []
  migrations: []
  compatibility: ""   # backward/forward strategy
  idempotency: ""     # if needed

integrations: []      # external systems + failure modes

tradeoffs: []         # "A vs B -> why -> impact"
risks: []             # "risk -> mitigation"

tests:
  heavy_definition: ""     # what is heavy (time/infra/cost)
  heavy_budget: ""         # when full is allowed
  defaults:
    profile: "fast"        # fast|targeted|full|none
    tasks: []              # runner tasks (gradle/npm/etc)
    filters: []            # test filters
  matrix:
    unit: []
    integration: []
    contract: []
    e2e_stand: []          # minimal smoke on stand

rollout:
  feature_flag: ""
  steps: []
  rollback: ""

observability:
  logs: []
  metrics: []
  alerts: []

open_questions:
  blocker: []
  non_blocker: []
```

---

## AIDD:NEXT_3
> Пока `AIDD:SPEC Status` не READY — сюда идут шаги интервью/refinement.
> После READY — 3 ближайших implement-чекбокса (каждый с DoD/Boundaries/Tests).
- [ ] <1. ближайший чекбокс (одна итерация)>
- [ ] <2. следующий>
- [ ] <3. третий>

---

## AIDD:HANDOFF_INBOX
> Сюда падают задачи из Research/Review/QA (с source: aidd/reports/...).
- [ ] Research: <title> — <recommendation> (source: aidd/reports/research/<ABC-123>-context.json)
- [ ] Review: <severity> <title> — <recommendation> (source: aidd/reports/reviewer/<ABC-123>.json)
- [ ] QA: <severity> <title> — <recommendation> (source: aidd/reports/qa/<ABC-123>.json)

---

## AIDD:INTERVIEW

> Глубокое интервью по plan. Вопросы только НЕочевидные (см. anchor tasklist).
> Ведём append-only очередь Q/A, чтобы не терять историю.

Passes:

- [ ] Pass 1 — UI/UX & journeys
- [ ] Pass 2 — Technical design & tradeoffs
- [ ] Pass 3 — Tests/Rollout/Observability
- [ ] Spec READY (AIDD:SPEC Status: READY)

Coverage checklist (DoD интервью):

- [ ] UI: happy + 3–5 edge/failure + loading/empty + permissions + a11y/i18n
- [ ] Tech: FE/BE/mobile границы + контракты + retries/error handling + idempotency
- [ ] Data: миграции/совместимость/консистентность
- [ ] Tradeoffs: A vs B → почему + последствия
- [ ] Tests: unit/integration/contract/e2e + heavy budget + когда FULL
- [ ] Rollout: flag + этапы + rollback
- [ ] No blocker open questions

Question queue (append-only):

- Q01:

  - Type: Clarification|Blocker
  - Question: ""
  - Why/Impact: ""
  - Options: ["A) ...", "B) ..."]
  - Default: ""
  - Answer: ""

## AIDD:DECISIONS

- <YYYY-MM-DD> Decision: ... (why / tradeoff / impact)

## AIDD:TEST_POLICY

> Политика, чтобы не запускать тяжелые тесты “каждый stop”.

- Default profile per checkbox: fast
- Heavy tests definition: <what>
- Heavy budget: <when we allow full>
- FULL is mandatory when:

  - changed: core/shared/config/build/infra OR risky integration
- TARGETED usage guide:

  - tasks examples: ...
  - filters examples: ...

## AIDD:OPEN_QUESTIONS

- (Blocker) ...
- (Non-blocker) ...

## AIDD:TASKLIST_REFINEMENT

> Цель: чекбоксы без разночтений. Каждый implement‑чекбокс имеет DoD/Boundaries/Tests.

- [ ] Pass A — Draft: задачи из plan → чекбоксы
- [ ] Pass B — Split: разбить большие пункты до 1-итерационных
- [ ] Pass C — Each checkbox has DoD/Boundaries/Tests (+ test profile/tasks/filters)
- [ ] Pass D — Stand/E2E: тест-данные, мок-стратегия, smoke на стенде
- [ ] Pass E — Final: нет TBD/TODO, AIDD:SPEC=READY

---

## AIDD:CHECKLIST

### AIDD:CHECKLIST_SPEC
- [ ] PRD: Status READY (и нет незакрытых blocker вопросов)
- [ ] Research: Status reviewed
- [ ] Plan: существует и валиден
- [ ] Review Spec: Plan Review READY + PRD Review READY
- [ ] Tasklist: AIDD:SPEC Status READY + coverage checklist закрыт

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
> Формат записи:
> `- YYYY-MM-DD Iteration N: <что сделано> (checkbox: <...>) (tests: <...>) (artifacts: <...>)`
- <YYYY-MM-DD> Iteration 1: ...

---

## AIDD:HOW_TO_UPDATE
- Правило итерации: **1 чекбокс** (или 2 тесно связанных) — затем Stop.
- Отмечайте чекбоксы так:
  - `- [x] <описание> — YYYY-MM-DD (iteration N) (tests: fast|targeted|full|none) (link: <commit/pr>)`
- Если меняются решения — сначала обнови `AIDD:SPEC_PACK` и `AIDD:DECISIONS`, затем чекбоксы.
- Логи/stacktrace не вставлять в tasklist — только ссылки на `aidd/reports/**`.
