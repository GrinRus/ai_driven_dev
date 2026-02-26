# Аудит AIDD по Context Engineering + сверка покрытия Wave 101 (оба среза)

schema: `aidd.context_audit.v2`  
generated_at: `2026-02-25`  
scope: `repo current state + Wave 101 planned coverage`

## Краткое резюме

- Базовый источник best practices: Anthropic, **September 29, 2025**: [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents).
- Текущий срез репозитория (as-is): **20/24** по 8 измерениям.
- Срез “после полного выполнения Wave 101”: прогноз **23/24**.
- Вывод: покрытие очень высокое, но пока не 100%.

Неполностью закрытые требования даже после текущего Wave 101 (до дополнения):
1. Унифицированный JIT chunk-tool contract (`peek/slice/search/split/get_chunk/subcall`) для всех классов артефактов.
2. First-class KPI контекста (не только pass/fail тесты и гейты).

## 1) Рамка требований (R1-R10)

1. `R1 Externalized context`: контекст в артефактах, не в чате.
2. `R2 Rules/guards first`: строгие правила доступа и safety hooks.
3. `R3 Retrieval-first`: pack/slice-first, full-read как fallback.
4. `R4 Safe tools`: безопасные инструменты чтения/записи + boundary enforcement.
5. `R5 Compaction`: budgets/trim/large-output handling.
6. `R6 Artifact loop`: tool/subcall -> artifact -> retrieval.
7. `R7 Context isolation`: stage/scope isolation.
8. `R8 Determinism`: схемы, стабильная сериализация, контрактные артефакты.
9. `R9 JIT primitives completeness`: не только `md_slice/rlm_slice`, а общий chunk-router.
10. `R10 Observability/evals`: диагностируемость + quality metrics на контур context engineering.

## 2) Текущий срез (as-is) с доказательствами

| Измерение | Score | Статус | Evidence |
| --- | --- | --- | --- |
| Externalized Context | 2/3 | partial | [precompact_snapshot.py](/Users/griogrii_riabov/.codex/worktrees/7875/ai_driven_dev/hooks/context_gc/precompact_snapshot.py), [working_set_builder.py](/Users/griogrii_riabov/.codex/worktrees/7875/ai_driven_dev/hooks/context_gc/working_set_builder.py), [loader.py](/Users/griogrii_riabov/.codex/worktrees/7875/ai_driven_dev/skills/aidd-core/runtime/reports/loader.py) |
| Retrieval-First | 2/3 | partial | [read-policy.md](/Users/griogrii_riabov/.codex/worktrees/7875/ai_driven_dev/skills/aidd-policy/references/read-policy.md), [rlm_slice.py](/Users/griogrii_riabov/.codex/worktrees/7875/ai_driven_dev/skills/aidd-rlm/runtime/rlm_slice.py), [md_slice.py](/Users/griogrii_riabov/.codex/worktrees/7875/ai_driven_dev/skills/aidd-docio/runtime/md_slice.py) |
| Safe Tooling | 3/3 | aligned | [pretooluse_guard.py](/Users/griogrii_riabov/.codex/worktrees/7875/ai_driven_dev/hooks/context_gc/pretooluse_guard.py), [context_expand.py](/Users/griogrii_riabov/.codex/worktrees/7875/ai_driven_dev/skills/aidd-docio/runtime/context_expand.py), [hooks.json](/Users/griogrii_riabov/.codex/worktrees/7875/ai_driven_dev/hooks/hooks.json) |
| Compaction | 2/3 | partial | [userprompt_guard.py](/Users/griogrii_riabov/.codex/worktrees/7875/ai_driven_dev/hooks/context_gc/userprompt_guard.py), [reports_pack_parts/core.py](/Users/griogrii_riabov/.codex/worktrees/7875/ai_driven_dev/skills/aidd-rlm/runtime/reports_pack_parts/core.py), [context_gc.json](/Users/griogrii_riabov/.codex/worktrees/7875/ai_driven_dev/templates/aidd/config/context_gc.json) |
| Artifact Loop | 3/3 | aligned | [loop_step_stage_chain.py](/Users/griogrii_riabov/.codex/worktrees/7875/ai_driven_dev/skills/aidd-loop/runtime/loop_step_stage_chain.py), [preflight_prepare.py](/Users/griogrii_riabov/.codex/worktrees/7875/ai_driven_dev/skills/aidd-loop/runtime/preflight_prepare.py), [actions_apply.py](/Users/griogrii_riabov/.codex/worktrees/7875/ai_driven_dev/skills/aidd-docio/runtime/actions_apply.py) |
| Context Isolation | 3/3 | aligned | [loop_pack_parts/core.py](/Users/griogrii_riabov/.codex/worktrees/7875/ai_driven_dev/skills/aidd-loop/runtime/loop_pack_parts/core.py), [implement CONTRACT](/Users/griogrii_riabov/.codex/worktrees/7875/ai_driven_dev/skills/implement/CONTRACT.yaml) |
| Determinism | 3/3 | aligned | [output_contract.py](/Users/griogrii_riabov/.codex/worktrees/7875/ai_driven_dev/skills/aidd-loop/runtime/output_contract.py), [reports_pack_parts/core.py](/Users/griogrii_riabov/.codex/worktrees/7875/ai_driven_dev/skills/aidd-rlm/runtime/reports_pack_parts/core.py) |
| Observability & Tests | 2/3 | partial | [doctor.py](/Users/griogrii_riabov/.codex/worktrees/7875/ai_driven_dev/skills/aidd-observability/runtime/doctor.py), [test_context_gc.py](/Users/griogrii_riabov/.codex/worktrees/7875/ai_driven_dev/tests/test_context_gc.py), [test_preflight_prepare.py](/Users/griogrii_riabov/.codex/worktrees/7875/ai_driven_dev/tests/test_preflight_prepare.py), [test_rlm_slice.py](/Users/griogrii_riabov/.codex/worktrees/7875/ai_driven_dev/tests/test_rlm_slice.py) |

Ключевой текущий gap:
- `Memory v2` в RFC есть, runtime отсутствует: [memory-v2-rfc.md](/Users/griogrii_riabov/.codex/worktrees/7875/ai_driven_dev/docs/memory-v2-rfc.md).
- `skills/aidd-memory` в текущем tree отсутствует.

## 3) Сверка с задачами Wave 101 (coverage check)

Источник: [backlog.md](/Users/griogrii_riabov/.codex/worktrees/7875/ai_driven_dev/backlog.md) (`W101-1..W101-26` на момент проверки).

### Что Wave 101 закрывает полностью

1. `R1/R6/R8` (memory + artifacts + determinism): `W101-1..W101-5`, `W101-10..W101-12`.
2. `R3/R4` в code retrieval (AST + fallback): `W101-16..W101-23`.
3. `R10` в regression/rollout: `W101-13`, `W101-19`, `W101-24`, `W101-26`.
4. Контрактное расширение read-chain policy: `W101-8`, `W101-11`, `W101-21`.

### Что покрыто частично

1. `R9 JIT primitives completeness`: AST adapter + packs есть (`W101-16..W101-20`), но нет явного unified `get_chunk/split` router для всех artifact classes.
2. `R10 quality evals`: есть тесты/гейты, но нет first-class KPI schema и агрегированного quality artifact.

## 4) Решение по вопросу “все ли покрыли”

- **Нет, не на 100%** (без добивающих задач).
- Wave 101 закрывает основной контур очень сильно, но для “полного закрытия” нужны отдельные closure-задачи.

## 5) Дополнение к Wave 101 для 100% closure

Добавлены в backlog:

1. `W101-27 (P1)` Unified JIT chunk router:
   - `skills/aidd-docio/runtime/chunk_query.py`
   - API: `--path/--query/--selector/--max-chars/--format json`
   - Artifact: `aidd/reports/context/<ticket>-chunk-<hash>.pack.json`
   - Tests: `tests/test_chunk_query.py`

2. `W101-28 (P1)` Context quality telemetry:
   - Artifact: `aidd/reports/observability/<ticket>.context-quality.json`
   - Fields: `pack_reads`, `slice_reads`, `full_reads`, `fallback_rate`, `context_expand_count_by_reason`, `output_contract_warn_rate`
   - Tests: `tests/test_context_quality_metrics.py`

3. `W101-29 (P2)` Policy guard modularization:
   - split `pretooluse_guard.py` -> `rw_policy`, `bash_guard`, `prompt_injection`, `rate_limit`
   - Tests: `tests/test_context_gc.py`, `tests/test_hook_rw_policy.py`

## 6) Важные изменения API/интерфейсов (после W101-27..29)

1. Новый runtime CLI: `chunk_query.py` (unified JIT query).
2. Новый observability artifact schema: `aidd.context_quality.v1`.
3. Расширение read-policy ссылкой на unified chunk path при сохранении `md_slice/rlm_slice`.

## 7) Тестовые сценарии (финальные acceptance)

1. Любой read вне readmap/writemap -> `deny/ask`.
2. Большие логи/чтения не раздувают чат, full output в `aidd/reports/**`.
3. Stage-chain материализует `preflight -> run -> postflight -> stage_result`.
4. `READ_LOG` сохраняет pack/slice-first порядок.
5. `chunk_query` одинаково работает на markdown/RLM/log/text и пишет pack artifact.
6. Quality KPI стабильно отражают fallback/full-read/context-expand pressure.

## 8) Assumptions / defaults

1. Сравнение выполнено в двух срезах: текущая реализация + плановое покрытие Wave 101.
2. Planned задачи считаются покрытием требований как roadmap, не как implemented state.
3. Базовый score current-state считается по 8 измерениям (0..3 каждое), без “зачета планов”.
4. Источник best practices фиксирован: Anthropic статья выше + Flow/JIT тезисы.
