# SDLC Flow (AIDD)

Канонический порядок стадий (variant B):

1. **idea** → `/idea-new` → `analyst`
2. **research** → `/researcher` → `researcher` (обязателен перед планированием)
3. **plan** → `/plan-new` → `planner` → `validator`
4. **review-plan** → `/review-spec` → `plan-reviewer`
5. **review-prd** → `/review-spec` → `prd-reviewer`
6. **spec-interview** (optional) → `/spec-interview` → `spec-interview-writer`
7. **tasklist** → `/tasks-new` → `tasklist-refiner`
8. **implement** → `/implement` → `implementer`
9. **review** → `/review` → `reviewer`
10. **qa** → `/qa` → `qa`

> `spec-interview` можно запускать как перед `/tasks-new`, так и после — для дополнительного уточнения.  
> Review-plan и review-prd выполняются только через `/review-spec` (не после каждого этапа).

## Таблица переходов

| Stage | Команда | Агент | Входы | Выходы | Гейт/условия |
| --- | --- | --- | --- | --- | --- |
| idea | `/idea-new` | `analyst` | PRD template, research (если есть) | PRD draft + вопросы + AIDD:RESEARCH_HINTS | Нет перехода в plan без ответов |
| research | `/researcher` | `researcher` | PRD, репозиторий | Research report (reviewed/pending) | `gate-workflow` требует reviewed |
| plan | `/plan-new` | `planner` + `validator` | PRD READY, research | План + статус validator | `research-check` обязателен перед планом |
| review-plan | `/review-spec` | `plan-reviewer` | План + research | `## Plan Review` в плане | Блокирует PRD review/`tasks` при BLOCKED |
| review-prd | `/review-spec` | `prd-reviewer` | PRD + plan + research | `## PRD Review` + report | Блокирует `tasks`/код при BLOCKED |
| spec-interview (optional) | `/spec-interview` | `spec-interview-writer` | Plan + PRD + research | Spec | Опционально до/после tasklist |
| tasklist | `/tasks-new` | `tasklist-refiner` | Plan (+ Spec) | Tasklist READY | Без tasklist нет implement |
| implement | `/implement` | `implementer` | Plan + tasklist (+ spec if exists) | Код + обновлённый tasklist | `gate-workflow`, `gate-tests` |
| review | `/review` | `reviewer` | Diff + tasklist | Findings + tasklist | `reviewer-tests` |
| qa | `/qa` | `qa` | Tasklist + отчёты | QA report | `gate-qa` |

## Инварианты

- Все артефакты находятся в `aidd/**`.
- Переход на следующую стадию допускается только при готовых артефактах и статусах из `status-machine.md`.
- Любое изменение порядка стадий требует обновления этого документа и гейтов.
- Команда `/review-spec` выполняет review-plan + review-prd, гейты требуют READY по обоим разделам.
