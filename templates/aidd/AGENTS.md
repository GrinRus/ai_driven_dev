# AGENTS

Единая точка входа для runtime‑агентов AIDD (workspace). Dev‑гайд репозитория: `AGENTS.md` в корне плагина.

## Skill-first канон
- Core policy: `${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/SKILL.md`.
- Loop policy: `${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/SKILL.md`.
- Этот документ — пользовательский обзор; не дублируйте алгоритмы из skills.
- Stage lexicon (public/internal): `aidd/docs/shared/stage-lexicon.md`.

## Базовые правила
- Все артефакты находятся в `aidd/**` (paths от root).
- Pack‑first/read‑budget, output‑контракт, question format, DocOps и subagent‑guard — см. `skills/aidd-core`.
- Loop discipline — см. `skills/aidd-loop`.
- Stage‑локальные entrypoints: `skills/<stage>/scripts/*` (canonical).
- Shared entrypoints: целевой canonical путь `skills/aidd-core/scripts/*`; до завершения миграции совместимость сохраняется через `tools/*.sh` shims.
- `tools/` — shared runtime library/orchestrator и compatibility shims на migration window.
- Wrapper‑вывод: stdout ≤ 200 lines или ≤ 50KB; stderr ≤ 50 lines; большие выводы пишите в `aidd/reports/**`.
- `AIDD_SKIP_STAGE_WRAPPERS=1` — только для диагностики; в `strict` и на стадиях `review|qa` это блокирующий режим (`reason_code=wrappers_skipped_unsafe`).

## Evidence read policy (summary)
- Primary evidence (research): `aidd/reports/research/<ticket>-rlm.pack.json`.
- Slice on demand: `${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/rlm-slice.sh --ticket <ticket> --query "<token>"`.

## Ответы пользователя
Ответы давайте в рамках той же команды (без смены стадии). Если ответы приходят в чате, попросите блок:
```
## AIDD:ANSWERS
- Answer 1: ...
- Answer 2: ...
```
