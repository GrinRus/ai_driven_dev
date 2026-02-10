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
- `AIDD:READ_LOG` обязателен для чтения артефактов и fallback full-read причин (см. `skills/aidd-core`).
- Loop discipline — см. `skills/aidd-loop`.
- Stage/shared runtime entrypoints: `skills/*/runtime/*.py` (Python-only canon).
- Shared entrypoints: canonical путь `skills/aidd-core/runtime/*.py`, `skills/aidd-loop/runtime/*.py`, `skills/aidd-rlm/runtime/*.py`.
- Shell wrappers допустимы только в hooks/platform glue; stage orchestration не должна зависеть от `skills/*/scripts/*`.
- `tools/` содержит только import stubs и repo-only tooling.
- Wrapper‑вывод: stdout ≤ 200 lines или ≤ 50KB; stderr ≤ 50 lines; большие выводы пишите в `aidd/reports/**`.
- `AIDD_SKIP_STAGE_WRAPPERS=1` — только для диагностики; в `strict` и на стадиях `review|qa` это блокирующий режим (`reason_code=wrappers_skipped_unsafe`).

## Evidence read policy (summary)
- Primary evidence (research): `aidd/reports/research/<ticket>-rlm.pack.json`.
- Slice on demand: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_slice.py --ticket <ticket> --query "<token>"`.

## Migration policy (legacy -> RLM-only)
- Legacy pre-RLM research context/targets artifacts не читаются гейтами и не считаются evidence.
- Для старого workspace состояния пересоберите research stage: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/researcher/runtime/research.py --ticket <ticket> --auto`.
- Если после research `rlm_status=pending`, выполните handoff на shared owner: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_finalize.py --ticket <ticket>`.
- Gate readiness для plan/review/qa требует минимальный RLM набор: `rlm-targets`, `rlm-manifest`, `rlm.worklist.pack`, `rlm.nodes`, `rlm.links`, `rlm.pack`.

## Ответы пользователя
Ответы давайте в рамках той же команды (без смены стадии). Если ответы приходят в чате, попросите блок:
```
## AIDD:ANSWERS
- Answer 1: ...
- Answer 2: ...
```
