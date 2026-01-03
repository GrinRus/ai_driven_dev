# SDLC Flow (AIDD)

Канонический порядок стадий (variant B):

1. **idea** → `/idea-new` → `analyst`
2. **research** → `/researcher` → `researcher` (при необходимости)
3. **plan** → `/plan-new` → `planner` → `validator`
4. **review-plan** → `/review-plan` → `plan-reviewer`
5. **review-prd** → `/review-prd` → `prd-reviewer`
6. **tasklist** → `/tasks-new`
7. **implement** → `/implement` → `implementer`
8. **review** → `/review` → `reviewer`
9. **qa** → `/qa` → `qa`

> Для удобства используйте `/review-spec`, чтобы выполнить review-plan и review-prd одной командой.

## Таблица переходов

| Stage | Команда | Агент | Входы | Выходы | Гейт/условия |
| --- | --- | --- | --- | --- | --- |
| idea | `/idea-new` | `analyst` | PRD template, research (если есть) | PRD draft + вопросы | Нет перехода в plan без ответов |
| research | `/researcher` | `researcher` | PRD, репозиторий | Research report (reviewed/pending) | `gate-workflow` требует reviewed |
| plan | `/plan-new` | `planner` + `validator` | PRD READY, research | План + статус validator | Без plan нет tasklist |
| review-plan | `/review-plan` | `plan-reviewer` | План + research | `## Plan Review` в плане | Блокирует `review-prd`/`tasks` при BLOCKED |
| review-prd | `/review-prd` | `prd-reviewer` | PRD + plan + research | `## PRD Review` + report | Блокирует `tasks`/код при BLOCKED |
| tasklist | `/tasks-new` | — | План + PRD | Tasklist READY | Без tasklist нет implement |
| implement | `/implement` | `implementer` | План + tasklist | Код + обновлённый tasklist | `gate-workflow`, `gate-tests` |
| review | `/review` | `reviewer` | Diff + tasklist | Findings + tasklist | `reviewer-tests` |
| qa | `/qa` | `qa` | Tasklist + отчёты | QA report | `gate-qa` |

## Инварианты

- Все артефакты находятся в `aidd/**`.
- Переход на следующую стадию допускается только при готовых артефактах и статусах из `status-machine.md`.
- Любое изменение порядка стадий требует обновления этого документа и гейтов.
- Команда `/review-spec` выполняет review-plan + review-prd, но гейты всё равно требуют READY по обоим разделам.
