# SDLC Flow (AIDD)

Канонический порядок стадий (variant B):

1. **idea** → `/feature-dev-aidd:idea-new` → `analyst`
2. **research** → `/feature-dev-aidd:researcher` → `researcher` (обязателен перед планированием)
3. **plan** → `/feature-dev-aidd:plan-new` → `planner` → `validator`
4. **review-plan** → `/feature-dev-aidd:review-spec` → `plan-reviewer`
5. **review-prd** → `/feature-dev-aidd:review-spec` → `prd-reviewer`
6. **spec-interview** (optional) → `/feature-dev-aidd:spec-interview` → `spec-interview-writer`
7. **tasklist** → `/feature-dev-aidd:tasks-new` → `tasklist-refiner`
8. **implement** → `/feature-dev-aidd:implement` → `implementer`
9. **review** → `/feature-dev-aidd:review` → `reviewer`
10. **qa** → `/feature-dev-aidd:qa` → `qa`

> `spec-interview` можно запускать как перед `/feature-dev-aidd:tasks-new`, так и после — для дополнительного уточнения.  
> Review-plan и review-prd выполняются только через `/feature-dev-aidd:review-spec` (не после каждого этапа).

## Таблица переходов

| Stage | Команда | Агент | Входы | Выходы | Гейт/условия |
| --- | --- | --- | --- | --- | --- |
| idea | `/feature-dev-aidd:idea-new` | `analyst` | PRD template, research (если есть) | PRD draft + вопросы + AIDD:RESEARCH_HINTS | Нет перехода в plan без ответов |
| research | `/feature-dev-aidd:researcher` | `researcher` | PRD, репозиторий | Research report (reviewed/pending) | `gate-workflow` требует reviewed |
| plan | `/feature-dev-aidd:plan-new` | `planner` + `validator` | PRD READY, research | План + статус validator | `research-check` обязателен перед планом |
| review-plan | `/feature-dev-aidd:review-spec` | `plan-reviewer` | План + research | `## Plan Review` в плане | Блокирует PRD review/`tasks` при BLOCKED |
| review-prd | `/feature-dev-aidd:review-spec` | `prd-reviewer` | PRD + plan + research | `## PRD Review` + report | Блокирует `tasks`/код при BLOCKED |
| spec-interview (optional) | `/feature-dev-aidd:spec-interview` | `spec-interview-writer` | Plan + PRD + research | Spec | Опционально до/после tasklist |
| tasklist | `/feature-dev-aidd:tasks-new` | `tasklist-refiner` | Plan (+ Spec) | Tasklist READY | Без tasklist нет implement |
| implement | `/feature-dev-aidd:implement` | `implementer` | Plan + tasklist (+ spec if exists) | Код + обновлённый tasklist | `gate-workflow`, `gate-tests` |
| review | `/feature-dev-aidd:review` | `reviewer` | Diff + tasklist | Findings + tasklist | `reviewer-tests` |
| qa | `/feature-dev-aidd:qa` | `qa` | Tasklist + отчёты | QA report | `gate-qa` |

## Инварианты

- Все артефакты находятся в `aidd/**`.
- Переход на следующую стадию допускается только при готовых артефактах и статусах из `status-machine.md`.
- Любое изменение порядка стадий требует обновления этого документа и гейтов.
- Команда `/feature-dev-aidd:review-spec` выполняет review-plan + review-prd, гейты требуют READY по обоим разделам.
