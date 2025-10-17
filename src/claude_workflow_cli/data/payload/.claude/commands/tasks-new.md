description: "Сформировать чеклист задач (docs/tasklist/<slug>.md) для фичи"
argument-hint: "<slug>"
allowed-tools: Read,Edit,Write,Grep,Glob
---
На основе `docs/plan/$1.md` обнови `docs/tasklist/$1.md`: синхронизируй чеклисты по этапам
(аналитика, разработка, QA, релиз), перенеси зависимые задачи и критерии приёмки. Убедись, что
фронт-маттер содержит ссылки на PRD/plan/research и актуальную дату `Updated`. Все action items из
`## PRD Review` (status approved) вынеси в отдельные чекбоксы. При необходимости разверни пресет
`feature-impl` — он обновляет блок `## $1` внутри tasklist c задачами Wave 7.
