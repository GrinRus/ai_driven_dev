# Product Backlog

## Wave 100 — Реальная параллелизация (scheduler + claim + parallel loop-run)

_Статус: план. Цель — запуск нескольких implementer/reviewer в параллель по независимым work items, безопасное распределение задач, отсутствие гонок артефактов, консолидация результатов._

### EPIC P — Task Graph (DAG) как источник для планирования
- [ ] **W100-1** `tools/task_graph.py`, `aidd/reports/taskgraph/<ticket>.json` (или `aidd/docs/taskgraph/<ticket>.yaml`):
  - парсер tasklist → DAG:
    - узлы: iterations (`iteration_id`) + handoff (`id: review:* / qa:* / research:* / manual:*`);
    - поля: deps/locks/expected_paths/priority/blocking/state;
    - node id: `iteration_id` или `handoff id`; state выводится из чекбокса + (опционально) stage_result.
  - вычисление `ready/runnable` и топологическая проверка (cycles/missing deps).
  **AC:** из tasklist строится корректный DAG; есть список runnable узлов.

- [ ] **W100-2** `tools/taskgraph-check.sh` (или расширение `tasklist-check.sh`):
  - валидировать: циклы, неизвестные deps, self-deps, пустые expected_paths (если требуется), конфликтующие locks (опционально).
  **AC:** CI/локальный чек ловит некорректные зависимости до запуска параллели.

### EPIC Q — Claim/Lock протокол для work items
- [ ] **W100-3** `tools/work_item_claim.py`, `tools/work-item-claim.sh`, `aidd/reports/locks/<ticket>/<id>.lock.json`:
  - claim/release/renew lock;
  - stale lock policy (ttl, force unlock);
  - в lock хранить `worker_id`, `created_at`, `last_seen`, `scope_key`, `branch/worktree`;
  - shared locks dir (например, `AIDD_LOCKS_DIR`) или orchestrator-only locks; атомарное создание (O_EXCL).
  **AC:** один узел не может быть взят двумя воркерами; stale locks диагностируются и снимаются по правилам; locks общие для всех воркеров.

### EPIC R — Scheduler: выбор runnable узлов под N воркеров
- [ ] **W100-4** `tools/scheduler.py`:
  - выбрать набор runnable узлов на N воркеров:
    - учитывать deps,
    - учитывать `locks`,
    - учитывать пересечения `expected_paths` (конфликт → не запускать параллельно; конфликт = общий top-level group или префикс),
    - сортировка: blocking → priority → plan order.
  **AC:** scheduler отдаёт набор независимых work items; не выдаёт конфликтующие по locks/paths.

- [ ] **W100-5** `tools/loop_pack.py` / `loop-pack.sh`:
  - уметь генерировать loop pack по конкретному work_item_id, а не только “следующий из NEXT_3”;
  - сохранять pack в per‑work‑item пути (Wave 87 уже подготовил).
  **AC:** можно собрать loop pack для любого узла DAG по id; pack содержит deps/locks/expected_paths/size_budget/tests для выбранного узла.

### EPIC S — Parallel loop-run (оркестрация воркеров)
- [ ] **W100-6** `tools/loop_run.py`:
  - добавить режим `--parallel N`:
    - получить runnable узлы от scheduler,
    - claim locks,
    - запустить N воркеров (каждый с явным `--work-item <id>` / `scope_key`),
    - собирать stage results и принимать решения (blocked/done/continue) по каждому узлу.
  **AC:** parallel loop-run запускает N независимых узлов и корректно реагирует на BLOCKED/DONE по каждому; определён контракт artifact root (shared vs per-worktree) и сбор результатов.

- [ ] **W100-7** `tools/worktree_manager.py` (или `tests/repo_tools/worktree.sh`):
  - подготовка isolated рабочих директорий на воркера:
    - `git worktree add` / отдельные ветки,
    - единый шаблон именования веток,
    - cleanup.
  **AC:** каждый воркер работает в изолированном worktree; определён способ записи артефактов (shared root или сбор из worktrees).

### EPIC T — Консолидация результатов обратно в основной tasklist
- [ ] **W100-8** `tools/tasklist_consolidate.py`, `tools/tasklist-normalize.sh`:
  - на основе stage_result + review_pack + tests_log:
    - отметить `[x]` для завершённых узлов,
    - обновить `AIDD:NEXT_3` из DAG runnable,
    - добавить `AIDD:PROGRESS_LOG` записи,
    - перенос/дедуп handoff задач.
  **AC:** после параллельного прогона tasklist обновляется детерминированно; без дублей; NEXT_3 корректен; дедуп handoff по стабильному id.

- [ ] **W100-9** `tools/reports/aggregate.py`:
  - агрегировать evidence в “ticket summary”:
    - ссылки на per‑work‑item tests logs,
    - список stage results,
    - сводка статусов узлов.
  **AC:** есть единый сводный отчёт по тикету и по узлам.

### EPIC U — Документация + регрессии
- [ ] **W100-10** `templates/aidd/docs/loops/README.md`, `templates/aidd/AGENTS.md`:
  - задокументировать parallel workflow:
    - deps/locks/expected_paths правила,
    - claim/release,
    - конфликт‑стратегию (paths overlap → serial),
    - policy: воркеры не редактируют tasklist в parallel‑mode (consolidate делает main).
  **AC:** понятная инструкция “как запускать parallel loop-run” + troubleshooting + policy для tasklist/артефактов.

- [ ] **W100-11** `tests/test_scheduler.py`, `tests/test_parallel_loop_run.py`, `tests/repo_tools/parallel-loop-regression.sh`:
  - тесты на DAG, scheduler, claim, параллельный раннер, консолидацию.
  **AC:** регрессии ловят гонки/перетирание артефактов/неверный выбор runnable; включены кейсы conflict paths/lock stale/worker crash.

## Wave 101 — Context Engineering Completion (Memory v2 + AST Index)

_Статус: план. Цель — полностью закрыть context engineering контур: file-based memory layer поверх pack-first/RLM pipeline + optional AST retrieval с deterministic fallback, compact artifacts, gates и observability._
_Rollout policy: Memory v2 — breaking-only, без обратной совместимости и без backfill legacy memory артефактов; AST integration — optional (`off|auto|required`) с fallback на `rg`, wave-1 scope: `research/plan/review-spec`._

### EPIC M1 — Canonical memory artifacts and runtime API

- [x] **W101-1 (P0) Create `aidd-memory` shared skill and canonical runtime surface** `skills/aidd-memory/SKILL.md`, `skills/aidd-memory/runtime/{memory_extract.py,decision_append.py,memory_pack.py,memory_slice.py,memory_verify.py}`, `.claude-plugin/plugin.json`, `tests/repo_tools/entrypoints-bundle.txt`:
  - завести owner skill `aidd-memory` и canonical Python entrypoints;
  - подключить skill metadata в plugin inventory.
  **AC:** в inventory присутствует shared skill `aidd-memory` с canonical runtime API.
  **Deps:** -
  **Regression/tests:** `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/smoke-workflow.sh`.
  **Effort:** S
  **Risk:** Low

- [x] **W101-2 (P0) Memory schemas + validator contract (`semantic/decisions/pack`)** `skills/aidd-core/runtime/schemas/aidd/*.json`, `skills/aidd-memory/runtime/memory_verify.py`, `tests/test_memory_verify.py`:
  - добавить схемы `aidd.memory.semantic.v1`, `aidd.memory.decision.v1`, `aidd.memory.decisions.pack.v1`;
  - реализовать schema+budget validation.
  **AC:** memory artifacts валидируются детерминированно; invalid payloads блокируются с reason codes.
  **Deps:** W101-1
  **Regression/tests:** `python3 -m pytest -q tests/test_memory_verify.py`.
  **Effort:** M
  **Risk:** Medium

- [x] **W101-3 (P0) Semantic extractor runtime (`memory_extract.py`) with deterministic pack budgets** `skills/aidd-memory/runtime/memory_extract.py`, `tests/test_memory_extract.py`:
  - извлекать `terms/defaults/constraints/invariants/open_questions` из `aidd/docs/*` и `aidd/reports/context/*.pack.md`;
  - писать `aidd/reports/memory/<ticket>.semantic.pack.json` c stable ordering и trim policy.
  **AC:** semantic pack генерируется для активного ticket и укладывается в budget.
  **Deps:** W101-2
  **Regression/tests:** `python3 -m pytest -q tests/test_memory_extract.py`.
  **Effort:** M
  **Risk:** Medium

- [x] **W101-4 (P0) Append-only decision log + decisions pack assembly** `skills/aidd-memory/runtime/decision_append.py`, `skills/aidd-memory/runtime/memory_pack.py`, `tests/test_memory_decisions.py`:
  - реализовать append-only `aidd/reports/memory/<ticket>.decisions.jsonl`;
  - собирать `aidd/reports/memory/<ticket>.decisions.pack.json` (active/superseded chain, conflict summary, top-N).
  **AC:** решения сохраняются как immutable log; decision pack отражает актуальное состояние без дублей.
  **Deps:** W101-2
  **Regression/tests:** `python3 -m pytest -q tests/test_memory_decisions.py`.
  **Effort:** M
  **Risk:** Medium

- [x] **W101-5 (P1) Targeted memory retrieval (`memory_slice.py`) aligned with pack-first read discipline** `skills/aidd-memory/runtime/memory_slice.py`, `tests/test_memory_slice.py`:
  - добавить query-based slice для semantic/decisions memory;
  - сохранять slice artifacts в `aidd/reports/context/`.
  **AC:** memory slice работает как targeted evidence path без full-read.
  **Deps:** W101-3, W101-4
  **Regression/tests:** `python3 -m pytest -q tests/test_memory_slice.py`.
  **Effort:** S
  **Risk:** Low

### EPIC M2 — Integration into existing flow (research -> loop -> docops)

- [x] **W101-6 (P0) Bootstrap/config wiring for memory layer** `templates/aidd/config/conventions.json`, `templates/aidd/config/gates.json`, `skills/aidd-init/runtime/init.py`, `templates/aidd/reports/memory/.gitkeep`:
  - добавить memory knobs (enable/budgets/read order hints);
  - сидировать `aidd/reports/memory/` при init.
  **AC:** новые workspace получают memory config + directories из коробки.
  **Deps:** W101-1
  **Regression/tests:** `python3 -m pytest -q tests/test_init_aidd.py`.
  **Effort:** S
  **Risk:** Low

- [x] **W101-7 (P0) Research pipeline hook: run `memory_extract` after RLM readiness** `skills/researcher/runtime/research.py`, `tests/test_research_command.py`:
  - после успешной сборки RLM artifacts запускать semantic extraction;
  - фиксировать memory artifacts в event/index paths.
  **AC:** `research.py --auto` генерирует semantic memory pack без ручного шага.
  **Deps:** W101-3, W101-6
  **Regression/tests:** `python3 -m pytest -q tests/test_research_command.py`.
  **Effort:** M
  **Risk:** Medium

- [x] **W101-8 (P1) Loop preflight/read policy integration for memory packs** `skills/aidd-loop/runtime/preflight_prepare.py`, `skills/aidd-loop/runtime/output_contract.py`, `hooks/context_gc/pretooluse_guard.py`, `tests/test_preflight_prepare.py`, `tests/test_output_contract.py`:
  - добавить memory artifacts в optional read chain/readmap для implement/review/qa;
  - разрешить policy-driven reads из `aidd/reports/memory/**`.
  **AC:** loop stages читают memory packs без policy-deny и с корректным read-order diagnostics.
  **Deps:** W101-3, W101-4
  **Regression/tests:** `python3 -m pytest -q tests/test_preflight_prepare.py tests/test_output_contract.py`.
  **Effort:** M
  **Risk:** Medium

- [x] **W101-9 (P1) Context-GC working set enrichment with bounded memory excerpts** `hooks/context_gc/working_set_builder.py`, `templates/aidd/config/context_gc.json`, `tests/test_wave95_policy_guards.py`:
  - добавить short excerpts из semantic/decisions packs в auto working set;
  - сохранить global char limits и deterministic truncation.
  **AC:** session start получает memory summary без превышения context budget.
  **Deps:** W101-6, W101-7
  **Regression/tests:** `python3 -m pytest -q tests/test_wave95_policy_guards.py`.
  **Effort:** S
  **Risk:** Low

- [x] **W101-10 (P0) DocOps/actions support for decision writes in loop mode** `skills/aidd-docio/runtime/actions_validate.py`, `skills/aidd-docio/runtime/actions_apply.py`, `skills/aidd-core/runtime/schemas/aidd/aidd.actions.v1.json`, `skills/implement/CONTRACT.yaml`, `skills/review/CONTRACT.yaml`, `skills/qa/CONTRACT.yaml`, `tests/test_wave93_validators.py`:
  - добавить action type `memory_ops.decision_append`;
  - разрешить controlled decision updates через actions path.
  **AC:** loop stage может писать decision log только через validated actions flow.
  **Deps:** W101-4
  **Regression/tests:** `python3 -m pytest -q tests/test_wave93_validators.py tests/test_context_expand.py`.
  **Effort:** M
  **Risk:** High

- [x] **W101-11 (P1) Read-policy/templates/index alignment for memory-first retrieval** `skills/aidd-policy/references/read-policy.md`, `skills/aidd-core/templates/context-pack.template.md`, `skills/status/runtime/index_sync.py`, `skills/aidd-core/templates/index.schema.json`, `tests/test_status.py`:
  - добавить memory packs в canonical read order;
  - отразить memory artifacts в index/report discovery.
  **AC:** policy/templates/status-index не расходятся с Memory v2 contract.
  **Deps:** W101-8
  **Regression/tests:** `python3 -m pytest -q tests/test_status.py tests/test_prompt_lint.py`.
  **Effort:** S
  **Risk:** Low

### EPIC M3 — Gates, regression suite, rollout

- [x] **W101-12 (P0) Gate support: soft/hard memory readiness for `plan/review/qa`** `skills/aidd-core/runtime/research_guard.py`, `skills/aidd-core/runtime/gate_workflow.py`, `tests/test_gate_workflow.py`, `tests/test_research_check.py`:
  - добавить configurable memory checks (`require_semantic_pack`, `require_decisions_pack`);
  - ввести reason codes для warn/block rollout.
  **AC:** при включённой политике gate детерминированно сигнализирует memory incompleteness.
  **Deps:** W101-6, W101-11
  **Regression/tests:** `python3 -m pytest -q tests/test_gate_workflow.py tests/test_research_check.py`.
  **Effort:** M
  **Risk:** High

- [x] **W101-13 (P0) End-to-end regression coverage for Memory v2** `tests/test_memory_*.py`, `tests/test_preflight_prepare.py`, `tests/test_output_contract.py`, `tests/repo_tools/smoke-workflow.sh`, `tests/repo_tools/ci-lint.sh`:
  - покрыть unit/integration/e2e сценарии generation/read/write/gates;
  - добавить smoke steps для memory artifacts lifecycle.
  **AC:** Memory v2 покрыт regression tests и не ломает текущие stage pipelines.
  **Deps:** W101-1..W101-12
  **Regression/tests:** `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/smoke-workflow.sh`.
  **Effort:** M
  **Risk:** Medium

- [x] **W101-14 (P1) Docs/changelog/operator guidance for Memory v2 rollout (breaking-only)** `AGENTS.md`, `README.md`, `README.en.md`, `templates/aidd/AGENTS.md`, `CHANGELOG.md`, `docs/memory-v2-rfc.md`:
  - обновить canonical docs под semantic/decision memory paths и rollout policy;
  - зафиксировать breaking rollout: без backward compatibility/backfill для legacy memory state.
  **AC:** docs/prompts/notes согласованы с runtime и тестовым контрактом Memory v2 и явно фиксируют breaking-only policy.
  **Deps:** W101-13
  **Regression/tests:** `python3 tests/repo_tools/lint-prompts.py --root .`, `tests/repo_tools/ci-lint.sh`.
  **Effort:** S
  **Risk:** Low

- [x] **W101-15 (P1) Update full flow prompt script for Memory v2 (`aidd_test_flow_prompt_ralph_script_full.txt`)** `aidd_test_flow_prompt_ralph_script_full.txt`, `tests/repo_tools/smoke-workflow.sh`:
  - обновить full-flow prompt script под Memory v2 read chain (`rlm.pack -> semantic.pack -> decisions.pack -> loop/context packs`);
  - убрать legacy compatibility/backfill шаги из сценария и acceptance flow.
  **AC:** full-flow prompt script соответствует Wave 101 контракту (breaking-only, no backfill) и используется как актуальный operator сценарий.
  **Deps:** W101-14
  **Regression/tests:** `tests/repo_tools/smoke-workflow.sh`.
  **Effort:** S
  **Risk:** Low

### EPIC M4 — Optional AST Index Integration (research/plan-first)

_Назначение EPIC: закрыть retrieval/tooling/compaction контур для code evidence в context engineering сценарии, сохраняя optional зависимость и deterministic fallback на `rg`._

- [x] **W101-16 (P0) Optional ast-index config contract + bootstrap defaults** `templates/aidd/config/conventions.json`, `templates/aidd/config/gates.json`, `skills/aidd-init/runtime/init.py`:
  - добавить `ast_index` section в bootstrap/config контракт;
  - default режим: optional + fallback (`mode=auto`, `required=false`);
  - отсутствие binary не должно hard-block'ить flow в optional режиме.
  **AC:** workspace seed содержит `ast_index` knobs; default поведение — fallback, не блокировка.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_init_aidd.py`.
  **Effort:** S
  **Risk:** Low

- [x] **W101-17 (P0) Shared runtime adapter for ast-index with deterministic fallback** `skills/aidd-core/runtime`, `skills/aidd-core/runtime/runtime.py`:
  - реализовать единый Python adapter: `detect/ensure-index/run-json/normalize`;
  - reason codes: `ast_index_binary_missing`, `ast_index_index_missing`, `ast_index_timeout`, `ast_index_json_invalid`, `ast_index_fallback_rg`.
  **AC:** adapter обеспечивает детерминированные reason codes и fallback path.
  **Deps:** W101-16
  **Regression/tests:** `python3 -m pytest -q tests/test_ast_index_adapter.py`.
  **Effort:** M
  **Risk:** Medium

- [x] **W101-18 (P1) AST evidence pack schema + deterministic artifact writer** `skills/aidd-core/runtime/schemas/aidd`, `skills/aidd-rlm/runtime/reports_pack_parts/core.py`:
  - добавить schema/serializer для `aidd/reports/research/<ticket>-ast.pack.json`;
  - enforce budget/trim/sort policy + stable serialization.
  **AC:** AST pack валиден, детерминирован и укладывается в budget.
  **Deps:** W101-17
  **Regression/tests:** `python3 -m pytest -q tests/test_ast_pack_schema.py tests/test_ast_pack_budget.py`.
  **Effort:** M
  **Risk:** Medium

- [x] **W101-19 (P1) Observability/doctor integration for ast-index readiness** `skills/aidd-observability/runtime/doctor.py`, `skills/aidd-observability/runtime/tools_inventory.py`:
  - добавить проверки availability/version/index status;
  - optional mode не фейлит `doctor`.
  **AC:** `doctor` диагностирует ast-index readiness и корректно различает optional/required modes.
  **Deps:** W101-16
  **Regression/tests:** `python3 -m pytest -q tests/test_doctor.py tests/test_tools_inventory.py`.
  **Effort:** S
  **Risk:** Low

- [ ] **W101-20 (P0) Researcher runtime integration (research-first rollout)** `skills/researcher/runtime/research.py`, `skills/researcher/templates/research.template.md`:
  - в `research.py --auto` включить ast-index path при enabled mode;
  - писать fallback markers/warnings без блокировки при `required=false`.
  **AC:** research pipeline генерирует AST pack при доступности ast-index и детерминированно деградирует на `rg` при недоступности.
  **Deps:** W101-7, W101-17, W101-18
  **Regression/tests:** `python3 -m pytest -q tests/test_research_command.py tests/test_ast_index_research_integration.py`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W101-21 (P1) Plan/review-spec consumption of AST evidence (non-blocking)** `skills/plan-new/runtime/research_check.py`, `skills/review-spec/runtime/prd_review_cli.py`, `skills/aidd-policy/references/read-policy.md`, `skills/aidd-core/templates/context-pack.template.md`:
  - включить AST pack в recommended read order после RLM pack;
  - отсутствие AST pack в optional mode не блокирует stage.
  **AC:** read-order расширен без регрессий текущего RLM-first поведения.
  **Deps:** W101-11, W101-20
  **Regression/tests:** `python3 -m pytest -q tests/test_research_check.py tests/test_review_spec.py`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W101-22 (P1) Prompt/skill wiring for research/plan roles** `skills/researcher/SKILL.md`, `skills/plan-new/SKILL.md`, `skills/review-spec/SKILL.md`, `agents`, `tests/repo_tools/lint-prompts.py`:
  - обновить deterministic guidance: `ast-index preferred, rg fallback`;
  - обновить prompt-version/baseline в соответствии с policy.
  **AC:** роли `researcher/planner/plan-reviewer/prd-reviewer` отражают optional ast-index flow и проходят prompt lint.
  **Deps:** W101-20
  **Regression/tests:** `python3 tests/repo_tools/prompt-version --help`, `python3 tests/repo_tools/lint-prompts.py --root .`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W101-23 (P0) Fallback policy and stage status contract** `skills/aidd-core/runtime/reports/events.py`, `skills/aidd-loop/runtime/output_contract.py`:
  - нормализовать логирование reason codes в events/output contracts;
  - optional mode => `WARN`, required mode => `BLOCKED` + deterministic next action.
  **AC:** fallback semantics единообразны в status/reporting слое.
  **Deps:** W101-8, W101-17, W101-20
  **Regression/tests:** `python3 -m pytest -q tests/test_output_contract.py tests/test_events.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W101-24 (P0) Full test suite for ast-index integration** `tests`, `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/smoke-workflow.sh`:
  - покрыть modes `off/auto/required`, missing binary, missing index, valid JSON path, fallback path;
  - добавить smoke profile со stubbed binary, не требующий внешней обязательной зависимости.
  **AC:** CI/smoke проходят в default profile без mandatory ast-index и покрывают fallback behavior.
  **Deps:** W101-13, W101-16..W101-23
  **Regression/tests:** `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/smoke-workflow.sh`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W101-25 (P1) Docs/changelog/operator runbook for AST extension** `README.md`, `README.en.md`, `AGENTS.md`, `CHANGELOG.md`:
  - задокументировать install/update/troubleshooting;
  - явно зафиксировать optional dependency и fallback semantics.
  **AC:** docs/changelog согласованы с unified Wave 101 runtime contract.
  **Deps:** W101-14, W101-24
  **Regression/tests:** `tests/repo_tools/ci-lint.sh`.
  **Effort:** S
  **Risk:** Low

- [ ] **W101-26 (P1) Rollout decision gate for wave-2 expansion (implement/review/qa)** `templates/aidd/config/gates.json`, `skills/aidd-observability/runtime/doctor.py`:
  - формализовать критерии wave-2 expansion (`quality`, `latency`, `fallback-rate` thresholds);
  - зафиксировать gate flags/policy для включения implement/review/qa scope.
  **AC:** rollout decisions для wave-2 детерминированы и проверяемы policy tests.
  **Deps:** W101-12, W101-24
  **Regression/tests:** `python3 -m pytest -q tests/test_gate_workflow.py tests/test_doctor.py`.
  **Effort:** S
  **Risk:** Low

- [ ] **W101-27 (P1) Unified JIT chunk router (`chunk_query`) across markdown/RLM/log/text** `skills/aidd-docio/runtime/chunk_query.py`, `skills/aidd-policy/references/read-policy.md`, `skills/aidd-core/templates/context-pack.template.md`:
  - добавить единый runtime API `chunk_query` с backend routing (`md_slice`, `rlm_slice`, generic file-chunk/log-chunk);
  - поддержать базовые JIT примитивы `peek/slice/search/split/get_chunk` в едином контракте CLI;
  - материализовать результат в `aidd/reports/context/<ticket>-chunk-<hash>.pack.json`.
  **AC:** один CLI покрывает markdown/jsonl/log/text и пишет deterministic chunk pack artifact.
  **Deps:** W101-18, W101-21
  **Regression/tests:** `python3 -m pytest -q tests/test_chunk_query.py`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W101-28 (P1) Context quality telemetry artifact + KPI counters** `skills/aidd-observability/runtime`, `skills/aidd-core/runtime/reports/events.py`, `skills/aidd-loop/runtime/output_contract.py`, `skills/researcher/runtime/research.py`, `skills/plan-new/runtime/research_check.py`:
  - добавить агрегированный артефакт `aidd/reports/observability/<ticket>.context-quality.json` (`schema: aidd.context_quality.v1`);
  - считать KPI: `pack_reads`, `slice_reads`, `full_reads`, `fallback_rate`, `context_expand_count_by_reason`, `output_contract_warn_rate`;
  - обновлять метрики в loop/research/plan путях без ломки текущих контрактов.
  **AC:** quality KPI стабильно формируются и пригодны для rollout decisions.
  **Deps:** W101-23, W101-24, W101-27
  **Regression/tests:** `python3 -m pytest -q tests/test_context_quality_metrics.py`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W101-29 (P2) Policy guard modularization (`pretooluse_guard` split)** `hooks/context_gc/pretooluse_guard.py`, `hooks/context_gc`:
  - декомпозировать `pretooluse_guard` на модули (`rw_policy`, `bash_guard`, `prompt_injection`, `rate_limit`);
  - сохранить поведение policy decisions (`allow/ask/deny`) и reason-code semantics;
  - снизить complexity hotspot без изменения публичного workflow контракта.
  **AC:** функциональное поведение эквивалентно текущему, модульность повышена, регрессий policy enforcement нет.
  **Deps:** W101-23
  **Regression/tests:** `python3 -m pytest -q tests/test_context_gc.py tests/test_hook_rw_policy.py`.
  **Effort:** M
  **Risk:** Medium

### Wave 101 Critical Path (unified)

1. `W101-1` -> `W101-2` -> `W101-3` + `W101-4` -> `W101-6` -> `W101-7`
2. `W101-4` -> `W101-10` -> `W101-8` -> `W101-11` -> `W101-12`
3. `W101-1..W101-12` -> `W101-13` -> `W101-14` -> `W101-15`
4. `W101-16` -> `W101-17` -> `W101-18` -> `W101-20` -> `W101-21`
5. `W101-17` -> `W101-23` -> `W101-24`
6. `W101-20` -> `W101-22` -> `W101-25`
7. `W101-12` + `W101-24` -> `W101-26`
8. `W101-18` + `W101-21` -> `W101-27` -> `W101-28`
9. `W101-23` -> `W101-29`
10. `W101-26` + `W101-28` + `W101-29` -> full context-engineering closure marker

### Wave 101 Important API/interfaces additions (AST + closure extension)

1. Новый optional config section: `ast_index` в workspace config.
2. Новый shared adapter API для deterministic ast-index execution + fallback.
3. Новый optional artifact: `aidd/reports/research/<ticket>-ast.pack.json`.
4. Новые reason codes для retrieval fallback/diagnostics.
5. Новый unified runtime CLI: `skills/aidd-docio/runtime/chunk_query.py`.
6. Новый observability artifact schema: `aidd.context_quality.v1`.
7. Внутренний policy refactor: модульная структура context-gc pretooluse guard.

### Wave 101 Test scenarios (AST + closure extension)

1. Binary missing, mode `auto`: stage продолжается на `rg` fallback с warning marker.
2. Binary missing, mode `required`: deterministic `BLOCKED` + next action.
3. Index missing и auto-bootstrap fail: `WARN+fallback` в `auto`, `BLOCKED` в `required`.
4. Valid ast-index JSON result: AST pack записан, schema/budgets соблюдены.
5. Research -> Plan path: AST pack участвует в read order без слома RLM-first semantics.
6. CI/smoke проходят без mandatory external binary в default profile.
7. `chunk_query` работает одинаково на markdown/RLM/log/text и пишет chunk pack artifact.
8. Context quality KPI стабильно отражают `pack/slice/full-read/fallback/context-expand/output-contract`.
9. После modularization `pretooluse_guard` поведение `allow/ask/deny` и reason codes не меняется.

### Wave 101 Assumptions and defaults (unified)

1. AST-блок интегрирован в `Wave 101` как `W101-16..W101-26`.
2. Dependency mode для AST части: `optional + fallback to rg`.
3. Rollout scope AST wave-1: `research/plan/review-spec`.
4. Без breaking change для минимально обязательных зависимостей (`python3`, `rg`, `git`) в AST части Wave 101.
5. Метка “100% context-engineering closure” считается достигнутой только после `W101-27..W101-29`.

### Wave 101 Delivery mode (execution)

1. Выбран режим поставки: **инкрементные PR-батчи**.
2. Запрещён перескок через `P0` dependencies из `W101-*`.
3. Каждый батч должен закрывать измеримый контракт (`runtime/API/artifacts/tests`), а не частичную заготовку.

### Wave 101 PR-batch execution plan (`W101-1..W101-29`)

| Batch | Tasks | Main output | Required checks | Exit criteria |
| --- | --- | --- | --- | --- |
| PR-01 `foundation-contracts` | `W101-1`, `W101-6`, `W101-16` | bootstrap contracts for `aidd-memory` + `ast_index` | `python3 -m pytest -q tests/test_init_aidd.py`, `tests/repo_tools/ci-lint.sh` | workspace seed содержит memory/ast knobs; skill/runtime surface зарегистрирован |
| PR-02 `memory-core-runtime` | `W101-2`, `W101-3`, `W101-4`, `W101-5` | memory schemas + extract/append/pack/slice runtime | `python3 -m pytest -q tests/test_memory_verify.py tests/test_memory_extract.py tests/test_memory_decisions.py tests/test_memory_slice.py` | deterministic generation/validation для `semantic.pack` и `decisions.pack` |
| PR-03 `memory-flow-readchain` | `W101-7`, `W101-8`, `W101-11` | memory read-chain integration в `research/loop/policy/templates` | `python3 -m pytest -q tests/test_research_command.py tests/test_preflight_prepare.py tests/test_output_contract.py tests/test_status.py` | pack-first read order включает memory artifacts без policy regressions |
| PR-04 `memory-governance` | `W101-9`, `W101-10`, `W101-12` | working-set enrichment + decision writes via validated actions + gates | `python3 -m pytest -q tests/test_wave95_policy_guards.py tests/test_wave93_validators.py tests/test_context_expand.py tests/test_gate_workflow.py tests/test_research_check.py` | soft/hard memory-gates и controlled writes работают детерминированно |
| PR-05 `memory-hardening-docs` | `W101-13`, `W101-14`, `W101-15` | memory e2e hardening + docs/changelog + prompt sync | `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/smoke-workflow.sh`, `python3 tests/repo_tools/lint-prompts.py --root .` | Memory v2 стабилен в e2e и задокументирован |
| PR-06 `ast-foundation` | `W101-17`, `W101-18`, `W101-19` | AST adapter + schema/writer + observability readiness | `python3 -m pytest -q tests/test_ast_index_adapter.py tests/test_ast_pack_schema.py tests/test_ast_pack_budget.py tests/test_doctor.py tests/test_tools_inventory.py` | optional AST path готов, fallback reason-codes стабильны |
| PR-07 `ast-flow-integration` | `W101-20`, `W101-21`, `W101-22`, `W101-23` | AST flow in `research/plan/review-spec` + status/fallback contract | `python3 -m pytest -q tests/test_research_command.py tests/test_ast_index_research_integration.py tests/test_research_check.py tests/test_review_spec.py tests/test_output_contract.py tests/test_events.py`, prompt lint/version checks | AST retrieval включён без регрессии RLM-first; optional/required semantics детерминированы |
| PR-08 `ast-regression-rollout` | `W101-24`, `W101-25`, `W101-26` | AST full regression + docs + rollout decision gate | `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/smoke-workflow.sh`, `python3 -m pytest -q tests/test_gate_workflow.py tests/test_doctor.py` | AST track production-ready в optional mode |
| PR-09 `closure-router-guard` | `W101-27`, `W101-29` | unified JIT `chunk_query` + modularized `pretooluse_guard` | `python3 -m pytest -q tests/test_chunk_query.py tests/test_context_gc.py tests/test_hook_rw_policy.py` | JIT router готов; policy behavior эквивалентен до/после refactor |
| PR-10 `closure-telemetry` | `W101-28` | context-quality KPI artifact (`aidd.context_quality.v1`) | `python3 -m pytest -q tests/test_context_quality_metrics.py`, `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/smoke-workflow.sh` | quality telemetry стабильна; closure marker для Wave 101 достигнут |

### Wave 101 High-risk regression gates

1. После `W101-10`, `W101-12`, `W101-23`, `W101-28` обязателен расширенный regression gate.
2. Для расширенного gate требуется минимум: профильные `pytest` + `tests/repo_tools/ci-lint.sh`.
3. Для финальных hardening батчей (`PR-05`, `PR-08`, `PR-10`) обязательны оба full checks: `ci-lint.sh` и `smoke-workflow.sh`.

### Wave 101 Merge policy

1. `SKILL.md`/`agents/*` изменения мержатся только с обновлением `prompt_version` и успешным `lint-prompts`.
2. User-facing изменения в runtime контрактах требуют синхронного docs/changelog обновления в wave batch.
3. Не объединять соседние батчи при незакрытых high-risk задачах (`W101-10`, `W101-12`, `W101-23`, `W101-28`).
4. Финальное закрытие Wave 101 фиксируется только при выполнении `W101-26 + W101-28 + W101-29`.
