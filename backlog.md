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

## Wave 101 — Memory v2 (semantic memory + decision log)

_Статус: план. Цель — полностью внедрить file-based memory layer поверх текущего pack-first/RLM pipeline: отдельный semantic pack, append-only decision log, deterministic retrieval и gate-ready интеграция._
_Rollout policy: breaking-only, без обратной совместимости и без backfill legacy артефактов._

### EPIC M1 — Canonical memory artifacts and runtime API

- [ ] **W101-1 (P0) Create `aidd-memory` shared skill and canonical runtime surface** `skills/aidd-memory/SKILL.md`, `skills/aidd-memory/runtime/{memory_extract.py,decision_append.py,memory_pack.py,memory_slice.py,memory_verify.py}`, `.claude-plugin/plugin.json`, `tests/repo_tools/entrypoints-bundle.txt`:
  - завести owner skill `aidd-memory` и canonical Python entrypoints;
  - подключить skill metadata в plugin inventory.
  **AC:** в inventory присутствует shared skill `aidd-memory` с canonical runtime API.
  **Deps:** -
  **Regression/tests:** `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/smoke-workflow.sh`.
  **Effort:** S
  **Risk:** Low

- [ ] **W101-2 (P0) Memory schemas + validator contract (`semantic/decisions/pack`)** `skills/aidd-core/runtime/schemas/aidd/*.json`, `skills/aidd-memory/runtime/memory_verify.py`, `tests/test_memory_verify.py`:
  - добавить схемы `aidd.memory.semantic.v1`, `aidd.memory.decision.v1`, `aidd.memory.decisions.pack.v1`;
  - реализовать schema+budget validation.
  **AC:** memory artifacts валидируются детерминированно; invalid payloads блокируются с reason codes.
  **Deps:** W101-1
  **Regression/tests:** `python3 -m pytest -q tests/test_memory_verify.py`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W101-3 (P0) Semantic extractor runtime (`memory_extract.py`) with deterministic pack budgets** `skills/aidd-memory/runtime/memory_extract.py`, `tests/test_memory_extract.py`:
  - извлекать `terms/defaults/constraints/invariants/open_questions` из `aidd/docs/*` и `aidd/reports/context/*.pack.md`;
  - писать `aidd/reports/memory/<ticket>.semantic.pack.json` c stable ordering и trim policy.
  **AC:** semantic pack генерируется для активного ticket и укладывается в budget.
  **Deps:** W101-2
  **Regression/tests:** `python3 -m pytest -q tests/test_memory_extract.py`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W101-4 (P0) Append-only decision log + decisions pack assembly** `skills/aidd-memory/runtime/decision_append.py`, `skills/aidd-memory/runtime/memory_pack.py`, `tests/test_memory_decisions.py`:
  - реализовать append-only `aidd/reports/memory/<ticket>.decisions.jsonl`;
  - собирать `aidd/reports/memory/<ticket>.decisions.pack.json` (active/superseded chain, conflict summary, top-N).
  **AC:** решения сохраняются как immutable log; decision pack отражает актуальное состояние без дублей.
  **Deps:** W101-2
  **Regression/tests:** `python3 -m pytest -q tests/test_memory_decisions.py`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W101-5 (P1) Targeted memory retrieval (`memory_slice.py`) aligned with pack-first read discipline** `skills/aidd-memory/runtime/memory_slice.py`, `tests/test_memory_slice.py`:
  - добавить query-based slice для semantic/decisions memory;
  - сохранять slice artifacts в `aidd/reports/context/`.
  **AC:** memory slice работает как targeted evidence path без full-read.
  **Deps:** W101-3, W101-4
  **Regression/tests:** `python3 -m pytest -q tests/test_memory_slice.py`.
  **Effort:** S
  **Risk:** Low

### EPIC M2 — Integration into existing flow (research -> loop -> docops)

- [ ] **W101-6 (P0) Bootstrap/config wiring for memory layer** `templates/aidd/config/conventions.json`, `templates/aidd/config/gates.json`, `skills/aidd-init/runtime/init.py`, `templates/aidd/reports/memory/.gitkeep`:
  - добавить memory knobs (enable/budgets/read order hints);
  - сидировать `aidd/reports/memory/` при init.
  **AC:** новые workspace получают memory config + directories из коробки.
  **Deps:** W101-1
  **Regression/tests:** `python3 -m pytest -q tests/test_init_aidd.py`.
  **Effort:** S
  **Risk:** Low

- [ ] **W101-7 (P0) Research pipeline hook: run `memory_extract` after RLM readiness** `skills/researcher/runtime/research.py`, `tests/test_research_command.py`:
  - после успешной сборки RLM artifacts запускать semantic extraction;
  - фиксировать memory artifacts в event/index paths.
  **AC:** `research.py --auto` генерирует semantic memory pack без ручного шага.
  **Deps:** W101-3, W101-6
  **Regression/tests:** `python3 -m pytest -q tests/test_research_command.py`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W101-8 (P1) Loop preflight/read policy integration for memory packs** `skills/aidd-loop/runtime/preflight_prepare.py`, `skills/aidd-loop/runtime/output_contract.py`, `hooks/context_gc/pretooluse_guard.py`, `tests/test_preflight_prepare.py`, `tests/test_output_contract.py`:
  - добавить memory artifacts в optional read chain/readmap для implement/review/qa;
  - разрешить policy-driven reads из `aidd/reports/memory/**`.
  **AC:** loop stages читают memory packs без policy-deny и с корректным read-order diagnostics.
  **Deps:** W101-3, W101-4
  **Regression/tests:** `python3 -m pytest -q tests/test_preflight_prepare.py tests/test_output_contract.py`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W101-9 (P1) Context-GC working set enrichment with bounded memory excerpts** `hooks/context_gc/working_set_builder.py`, `templates/aidd/config/context_gc.json`, `tests/test_wave95_policy_guards.py`:
  - добавить short excerpts из semantic/decisions packs в auto working set;
  - сохранить global char limits и deterministic truncation.
  **AC:** session start получает memory summary без превышения context budget.
  **Deps:** W101-6, W101-7
  **Regression/tests:** `python3 -m pytest -q tests/test_wave95_policy_guards.py`.
  **Effort:** S
  **Risk:** Low

- [ ] **W101-10 (P0) DocOps/actions support for decision writes in loop mode** `skills/aidd-docio/runtime/actions_validate.py`, `skills/aidd-docio/runtime/actions_apply.py`, `skills/aidd-core/runtime/schemas/aidd/aidd.actions.v1.json`, `skills/implement/CONTRACT.yaml`, `skills/review/CONTRACT.yaml`, `skills/qa/CONTRACT.yaml`, `tests/test_wave93_validators.py`:
  - добавить action type `memory_ops.decision_append`;
  - разрешить controlled decision updates через actions path.
  **AC:** loop stage может писать decision log только через validated actions flow.
  **Deps:** W101-4
  **Regression/tests:** `python3 -m pytest -q tests/test_wave93_validators.py tests/test_context_expand.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W101-11 (P1) Read-policy/templates/index alignment for memory-first retrieval** `skills/aidd-policy/references/read-policy.md`, `skills/aidd-core/templates/context-pack.template.md`, `skills/status/runtime/index_sync.py`, `skills/aidd-core/templates/index.schema.json`, `tests/test_status.py`:
  - добавить memory packs в canonical read order;
  - отразить memory artifacts в index/report discovery.
  **AC:** policy/templates/status-index не расходятся с Memory v2 contract.
  **Deps:** W101-8
  **Regression/tests:** `python3 -m pytest -q tests/test_status.py tests/test_prompt_lint.py`.
  **Effort:** S
  **Risk:** Low

### EPIC M3 — Gates, regression suite, rollout

- [ ] **W101-12 (P0) Gate support: soft/hard memory readiness for `plan/review/qa`** `skills/aidd-core/runtime/research_guard.py`, `skills/aidd-core/runtime/gate_workflow.py`, `tests/test_gate_workflow.py`, `tests/test_research_check.py`:
  - добавить configurable memory checks (`require_semantic_pack`, `require_decisions_pack`);
  - ввести reason codes для warn/block rollout.
  **AC:** при включённой политике gate детерминированно сигнализирует memory incompleteness.
  **Deps:** W101-6, W101-11
  **Regression/tests:** `python3 -m pytest -q tests/test_gate_workflow.py tests/test_research_check.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W101-13 (P0) End-to-end regression coverage for Memory v2** `tests/test_memory_*.py`, `tests/test_preflight_prepare.py`, `tests/test_output_contract.py`, `tests/repo_tools/smoke-workflow.sh`, `tests/repo_tools/ci-lint.sh`:
  - покрыть unit/integration/e2e сценарии generation/read/write/gates;
  - добавить smoke steps для memory artifacts lifecycle.
  **AC:** Memory v2 покрыт regression tests и не ломает текущие stage pipelines.
  **Deps:** W101-1..W101-12
  **Regression/tests:** `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/smoke-workflow.sh`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W101-14 (P1) Docs/changelog/operator guidance for Memory v2 rollout (breaking-only)** `AGENTS.md`, `README.md`, `README.en.md`, `templates/aidd/AGENTS.md`, `CHANGELOG.md`, `docs/memory-v2-rfc.md`:
  - обновить canonical docs под semantic/decision memory paths и rollout policy;
  - зафиксировать breaking rollout: без backward compatibility/backfill для legacy memory state.
  **AC:** docs/prompts/notes согласованы с runtime и тестовым контрактом Memory v2 и явно фиксируют breaking-only policy.
  **Deps:** W101-13
  **Regression/tests:** `python3 tests/repo_tools/lint-prompts.py --root .`, `tests/repo_tools/ci-lint.sh`.
  **Effort:** S
  **Risk:** Low

- [ ] **W101-15 (P1) Update full flow prompt script for Memory v2 (`dev/prompts/ralph/aidd_test_flow_prompt_ralph_script_full.txt`)** `dev/prompts/ralph/aidd_test_flow_prompt_ralph_script_full.txt`, `tests/repo_tools/smoke-workflow.sh`:
  - обновить full-flow prompt script под Memory v2 read chain (`rlm.pack -> semantic.pack -> decisions.pack -> loop/context packs`);
  - убрать legacy compatibility/backfill шаги из сценария и acceptance flow.
  **AC:** full-flow prompt script соответствует Wave 101 контракту (breaking-only, no backfill) и используется как актуальный operator сценарий.
  **Deps:** W101-14
  **Regression/tests:** `tests/repo_tools/smoke-workflow.sh`.
  **Effort:** S
  **Risk:** Low

### Wave 101 Critical Path

1. `W101-1` -> `W101-2` -> `W101-3` + `W101-4` -> `W101-6` -> `W101-7`
2. `W101-4` -> `W101-10` -> `W101-8` -> `W101-11` -> `W101-12`
3. `W101-1..W101-12` -> `W101-13` -> `W101-14` -> `W101-15`
