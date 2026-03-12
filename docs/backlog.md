# Product Backlog

> INTERNAL/DEV-ONLY: engineering wave planning and execution tracker.

_Revision note (2026-03-10): backlog ревизован по критерию удаления реализованных волн: удаляем волну только если acceptance подтверждён в текущем коде, релевантные regression/check команды зелёные, и нет открытых блокирующих зависимостей._

## Wave 109 — Carry-over from PR #109 (deduped)

_Статус: plan. Источник — PR #109 (`codex/w104-tst001-flow-remediation`), после дедупликации с текущими Wave 107/108/104. В секцию включены только пункты, не покрытые текущим backlog по сигнатуре проблемы + runtime/test контуру + AC._

- [ ] **W109-1 (P0) Remove non-canonical `set_stage.py` drift in plan stage** `skills/plan-new/SKILL.md`, `agents/planner.md`, `skills/plan-new/runtime/*`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - убрать обращения к `skills/aidd-flow-state/runtime/set_stage.py` и legacy summary handoff;
  - закрепить canonical routing через `set_active_stage.py` + tripwire на `can't open file ... set_stage.py`.
  **AC:** `plan-new` логи не содержат `set_stage.py` ошибок; stage завершает top-level result без runtime path drift.

- [ ] **W109-2 (P0) Remove tasks-new CLI drift (`progress_cli --message`)** `skills/tasks-new/SKILL.md`, `agents/tasklist-refiner.md`, `skills/tasks-new/runtime/tasks_new.py`, `tests/test_tasks_new.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - убрать non-canonical аргумент `--message` из prompt/runtime path для `progress_cli.py`;
  - зафиксировать canonical вызов progress CLI и добавить regression tripwire.
  **AC:** в `tasks-new` логах отсутствует `progress_cli.py: error: unrecognized arguments: --message`.

- [ ] **W109-3 (P0) Implement-stage fail-fast for repeated `command_not_found`** `skills/implement/runtime/implement_run.py`, `skills/implement/SKILL.md`, `agents/implementer.md`, `tests/test_implement_agent.py`, `tests/test_loop_step.py`:
  - детектировать повторяющиеся `exit 127`/`no such file or directory` (например, `./gradlew`) как terminal prompt-exec incident;
  - возвращать явный `reason_code` и canonical next action вместо long-running stall.
  **AC:** implement stage не уходит в silent stall при повторяющемся `command_not_found`.

- [ ] **W109-4 (P0) Stage-result enum hardening for review/qa mapping** `skills/review/**`, `skills/qa/**`, `skills/aidd-flow-state/runtime/stage_result.py`, `tests/test_review_agent.py`, `tests/test_qa_exit_code.py`:
  - запретить передачу non-canonical `--result` значений (`revise_required`, `conditional_pass`);
  - ввести deterministic mapping user-facing verdict -> canonical result (`blocked|continue|done`) до runtime вызова.
  **AC:** в review/qa логах отсутствует `stage_result.py: error: argument --result: invalid choice`.

- [ ] **W109-5 (P1) QA blocked reason-code completeness** `skills/qa/runtime/qa_parts/core.py`, `skills/qa/runtime/qa.py`, `skills/aidd-flow-state/runtime/stage_result.py`, `tests/test_qa_agent.py`, `tests/test_qa_exit_code.py`:
  - для blocked findings выставлять canonical `reason_code=blocking_findings`;
  - сохранить совместимость `schema=aidd.stage_result.v1` и evidence links contract.
  **AC:** blocked QA stage-result содержит непустой canonical reason code.

- [ ] **W109-6 (P1) Readiness recovery telemetry supersede markers** `tests/repo_tools/e2e_prompt/*`, `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - после успешного recovery (`readiness_gate=PASS`) помечать ранние `*_skipped_*`/`05_gate_outcome` как superseded;
  - убрать противоречивые terminal narrative при фактическом downstream execution.
  **AC:** итоговый step-5 audit status не содержит конфликтующих `NOT VERIFIED` при реально выполненных downstream шагах.

- [ ] **W109-7 (P1) Regression guard for TST-001 runs `20260308`/`20260309`** `tests/repo_tools/test_e2e_prompt_contract.py`, `tests/repo_tools/smoke-workflow.sh`, `tests/repo_tools/ci-lint.sh`:
  - добавить контрактные проверки на сигнатуры: `set_stage.py` drift, `progress_cli --message`, repeated `exit 127`, invalid stage-result enum, empty QA reason code, stale readiness telemetry conflict;
  - отделить допускаемые WARN от terminal blockers в expected matrix.
  **AC:** перечисленные сигнатуры ловятся repo-tools до merge.

## Wave 107 — TST-001 (2026-03-10) seed-stage failures remediation

_Статус: plan. Основание — аудит `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-001/20260310T050638Z` (terminal FAIL на шаге 6, downstream `NOT VERIFIED` на шагах 7/8). Цель — убрать `watchdog_terminated + result_count=0`, зафиксировать canonical orchestration и снизить false WARN в post-run классификации._

- [ ] **W107-1 (P0) Manual stage-result write hard-block + canonical-only handoff** `skills/aidd-core/runtime/stage_actions_run.py`, `skills/aidd-core/runtime/skill_contract_validate.py`, `skills/implement/SKILL.md`, `skills/review/SKILL.md`, `tests/test_stage_actions_run.py`, `tests/test_prompt_lint.py`, `tests/test_runtime_write_safety.py`:
  - запретить manual write-path в runtime/promptах для `aidd/reports/loops/**/stage.*.result.json` и `aidd/reports/logs/**/stage.*.log` как primary recovery path;
  - при попытке manual path возвращать canonical terminal payload (`reason_code=policy_violation_stage_result_manual_write`) вместо продолжения run;
  - закрепить lint-tripwire на non-canonical stage-chain recovery hints.
  **AC:** сценарий из `06_implement_run1.log` (ручные записи `stage.preflight.result.json`/`stage.result.json`) больше не воспроизводится; stage завершает run только canonical `aidd.stage_result.v1`.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_stage_actions_run.py tests/test_prompt_lint.py tests/test_runtime_write_safety.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W107-2 (P0) Seed-stage convergence contract for `implement/review` (no top-level result guard)** `skills/implement/runtime/implement_run.py`, `skills/review/runtime/review_run.py`, `skills/aidd-loop/runtime/loop_run_parts/core.py`, `tests/test_review_run.py`, `tests/test_loop_run.py`, `tests/test_qa_exit_code.py`:
  - ввести deterministic convergence guard: если run живой, но top-level result не эмитится в bounded window, возвращать canonical terminal payload до watchdog kill;
  - при `task_started` без `task_completed` возвращать explicit `blocked`/`warn` reason вместо hanging до budget exhaustion;
  - синхронизовать `exit_code/reason_code/watchdog_marker` mapping для seed stages.
  **AC:** кейсы из `06_implement_run1.summary.txt` и `06_review_run3_debug.summary.txt` не завершаются `result_count=0`; top-level result всегда присутствует при terminal завершении стадии.
  **Deps:** W107-1
  **Regression/tests:** `python3 -m pytest -q tests/test_review_run.py tests/test_loop_run.py tests/test_qa_exit_code.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W107-3 (P0) Launcher/liveness hardening for zero-byte and stream-path-not-emitted cases** `tests/repo_tools/aidd_stage_launcher.py`, `tests/repo_tools/aidd_stream_paths.py`, `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/test_aidd_stage_launcher.py`, `tests/repo_tools/test_aidd_audit_runner.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - стабилизировать shell-safe retry при `0 bytes` launcher anomaly (ровно один retry, с явным evidence marker);
  - унифицировать fallback discovery для stream-path extraction при `stream_path_not_emitted_by_cli=1`;
  - гарантировать корректную классификацию `silent stall` только при подтверждённой стагнации main+stream.
  **AC:** сценарий из `06_review_run1.summary.txt`/`06_review_stream_paths_run2.txt` детерминированно классифицируется и не даёт ложных terminal переходов при активном stream.
  **Deps:** W107-2
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_aidd_stage_launcher.py tests/repo_tools/test_aidd_audit_runner.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W107-4 (P1) `review-spec` narrative/report parity + pack-budget trimming** `skills/aidd-core/runtime/prd_review.py`, `skills/aidd-core/runtime/prd_review_section.py`, `tests/test_prd_review_agent.py`, `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - убрать расхождение narrative vs structured report при `recommended_status` вычислении;
  - стабилизировать top-N trimming для `action_items`, чтобы pack-budget exceed не приводил к contradictory verdicts;
  - зафиксировать report payload как единственный source-of-truth для recovery decisions.
  **AC:** `05_review_spec_report_check_run2.txt`-подобный `narrative_vs_report_mismatch=1` не воспроизводится при повторяемом run.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_prd_review_agent.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W107-5 (P1) Workspace-layout classifier baseline awareness (pre-existing root paths)** `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/test_aidd_audit_runner.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - отличать pre-existing root `docs|reports|config|.cache` от путей, созданных/изменённых в рамках текущего run;
  - по неизменённым pre-existing путям выдавать `INFO(preexisting_noncanonical_root)` вместо WARN;
  - сохранять WARN только для фактической мутации root non-canonical paths during run.
  **AC:** кейс из `99_workspace_layout_check.txt` не поднимает WARN при отсутствии delta во время аудита.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_aidd_audit_runner.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** S
  **Risk:** Low

- [ ] **W107-6 (P0) TST-001 20260310/20260311 regression fixture pack + replay checks** `tests/fixtures/audit_tst001_20260310/*`, `tests/fixtures/audit_tst001_20260311/*`, `tests/repo_tools/test_aidd_audit_runner.py`, `tests/repo_tools/test_aidd_stage_launcher.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - добавить минимальный fixture-set из аудитов 2026-03-10 и 2026-03-11 (step6 summaries, termination attribution, manual stage-result write excerpts, stream-path fallback artifacts, `tasks-new` nested unknown-skill signal, tasklist parser mismatch signal);
  - покрыть replay-проверками классификации `watchdog_terminated`, `no_top_level_result`, `silent_stall`, `stream_path_not_emitted_by_cli`, `review_spec_report_mismatch`, `prompt_flow_drift_recovered_unknown_skill_nested`, `tasklist_schema_parser_mismatch_recoverable`;
  - включить fixture replay в CI smoke/prompt-contract checks.
  **AC:** классификация инцидентов из TST-001 (включая nested unknown-skill drift в `tasks-new`) воспроизводится тестами детерминированно и ловит регрессии до e2e-аудита.
  **Deps:** W107-2, W107-3, W107-4
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_aidd_audit_runner.py tests/repo_tools/test_aidd_stage_launcher.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W107-7 (P0) Tasks-new nested skill resolution guard (`spec-interview-writer`)** `skills/tasks-new/runtime/tasks_new.py`, `skills/tasks-new/SKILL.md`, `agents/tasklist-refiner.md`, `tests/test_tasks_new.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - устранить nested invocation drift с `Unknown skill: feature-dev-aidd:spec-interview-writer` в `tasks-new` flow (alias/registry guard + canonical fallback/abort policy);
  - зафиксировать deterministic поведение при недоступности nested skill: без silent recovery-loop и без ложного top-level `READY` при критическом nested fail;
  - добавить regression tripwire на nested unknown-skill сигнатуру в `tasks-new` логах.
  **AC:** `tasks-new` happy-path по фикстуре TST-001 завершается с `unknown_skill_nested_hits=0`; при инъекции недоступного nested skill stage возвращает deterministic canonical classification.
  **Deps:** W107-6
  **Regression/tests:** `python3 -m pytest -q tests/test_tasks_new.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** S
  **Risk:** Medium

## Wave 108 — Loop soft-gate for Research (temporary)

_Статус: plan. Цель — не блокировать loop на `research_status_invalid` во время стабилизации research, затем вернуть строгий gate после исправлений._

- [ ] **W108-1** Stabilize Researcher/RLM links for `no_symbols` cases (`skills/aidd-rlm/runtime/rlm_links_build.py`, `skills/researcher/runtime/research.py`, `tests/test_rlm_links_build.py`, `tests/test_research_command.py`):
  - снизить ложные `links_empty_reason=no_symbols` на реальных backend/frontend кодовых базах;
  - добавить диагностику (какие target files/symbol sources отброшены и почему).
  **AC:** на репрезентативных тикетах `research --auto` перестаёт массово застревать в `Status: warn` из-за `no_symbols`.

- [ ] **W108-2** Add observability for loop research soft-gate usage (`skills/aidd-loop/runtime/loop_run_parts/core.py`, `tests/test_loop_run.py`):
  - фиксировать отдельный telemetry marker для soft-continue на `research_status_invalid`;
  - добавить сводный отчёт частоты soft-gate с reason codes в loop artifacts.
  - Findings (2026-03-03): в policy probe `qa_tests_failed` `ralph` корректно маркирует `recoverable_blocked=1`, `retry_attempt=1`, `recovery_path=handoff_to_implement`; `strict` остаётся terminal blocked (`recoverable_blocked=0`).
    Evidence: `.aidd_audit/loop_policy/20260303T080709Z/findings_summary_20260303.md`.
  **AC:** по логам/pack можно детерминированно увидеть, где loop стартовал через soft-gate.

- [ ] **W108-3** Return strict research gate after stabilization (`skills/aidd-loop/runtime/loop_run_parts/core.py`, `templates/aidd/config/gates.json`, `tests/test_loop_run.py`, `tests/repo_tools/e2e_prompt/profile_full.md`):
  - вернуть fail-fast блокировку `research_status_invalid` (через policy/config flag + rollout plan);
  - обновить e2e prompt contract и smoke/regression проверки.
  - Findings (2026-03-03): для non-recoverable причины (`review_pack_missing`) `strict` и `ralph` дают одинаковый terminal blocked (retry не запускается); rollback-план должен явно разделять recoverable/non-recoverable reason classes.
    Evidence: `.aidd_audit/loop_policy/20260303T080709Z/findings_summary_20260303.md`, `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/aidd/reports/loops/TST-001/cli.loop-run.20260303-080259.log`, `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/aidd/reports/loops/TST-001/cli.loop-run.20260303-080315.log`.
  **AC:** strict mode снова блокирует loop при неконсистентном research; есть подтверждённый rollout toggle и тесты.

- [ ] **W108-4** Keep loop scope-mismatch as non-terminal telemetry for post-review iteration rework (`skills/aidd-loop/runtime/loop_step_parts/core.py`, `tests/test_loop_step.py`):
  - сохранить soft-continue поведение при fallback `scope_key` mismatch в implement переходе;
  - фиксировать `scope_key_mismatch_warn`, `expected_scope_key`, `selected_scope_key` как обязательную telemetry поверхность.
  - Findings (2026-03-03): на `TST-001` mismatch больше не является terminal blocker; flow продолжает выполнение и упирается в downstream причину (`review_pack_missing`), что подтверждает корректность soft-mode только для mismatch gate.
    Evidence: `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/aidd/reports/loops/TST-001/cli.loop-step.20260303-080315.log`.
  **AC:** loop не падает terminal на mismatch и продолжает итерацию, а mismatch детерминированно виден в payload/логах.

- [ ] **W108-5** Re-introduce strict scope mismatch transition gate after canonical scope emit hardening (`skills/aidd-loop/runtime/loop_step_parts/core.py`, `skills/aidd-loop/runtime/loop_step_stage_chain.py`, `tests/test_loop_step.py`, `tests/repo_tools/e2e_prompt/profile_full.md`):
  - после стабилизации stage_result emission вернуть fail-fast блокировку `scope_mismatch_transition_blocked` за feature-flag/policy toggle;
  - покрыть rollout тестами и e2e профилями (strict vs temporary soft mode).
  - Findings (2026-03-03): synthetic probe с `blocking_findings` на review показывает нормализацию blocked→continue и downstream terminal по `review_pack_missing`; перед возвратом strict mismatch gate нужно зафиксировать границы нормализации warn-reasons.
    Evidence: `.aidd_audit/loop_policy/20260303T080709Z/findings_summary_20260303.md`.
  **AC:** strict profile снова блокирует non-authoritative fallback scope, rollout контролируется конфигом и подтверждён тестами.

## Wave 100 — Реальная параллелизация (scheduler + claim + parallel loop-run)

_Статус: plan. Цель — запуск нескольких implementer/reviewer в параллель по независимым work items, безопасное распределение задач, отсутствие гонок артефактов, консолидация результатов._

### EPIC P — Task Graph (DAG) как источник для планирования
- [ ] **W100-1** `skills/aidd-flow-state/runtime/task_graph.py`, `aidd/reports/taskgraph/<ticket>.json` (или `aidd/docs/taskgraph/<ticket>.yaml`):
  - парсер tasklist → DAG:
    - узлы: iterations (`iteration_id`) + handoff (`id: review:* / qa:* / research:* / manual:*`);
    - поля: deps/locks/expected_paths/priority/blocking/state;
    - node id: `iteration_id` или `handoff id`; state выводится из чекбокса + (опционально) stage_result.
  - вычисление `ready/runnable` и топологическая проверка (cycles/missing deps).
  **AC:** из tasklist строится корректный DAG; есть список runnable узлов.

- [ ] **W100-2** `skills/aidd-flow-state/runtime/taskgraph_check.py` (или расширение `skills/aidd-flow-state/runtime/tasklist_check.py`):
  - валидировать: циклы, неизвестные deps, self-deps, пустые expected_paths (если требуется), конфликтующие locks (опционально).
  **AC:** CI/локальный чек ловит некорректные зависимости до запуска параллели.

### EPIC Q — Claim/Lock протокол для work items
- [ ] **W100-3** `skills/aidd-loop/runtime/work_item_claim.py`, `aidd/reports/locks/<ticket>/<id>.lock.json`:
  - claim/release/renew lock;
  - stale lock policy (ttl, force unlock);
  - в lock хранить `worker_id`, `created_at`, `last_seen`, `scope_key`, `branch/worktree`;
  - shared locks dir (например, `AIDD_LOCKS_DIR`) или orchestrator-only locks; атомарное создание (O_EXCL).
  **AC:** один узел не может быть взят двумя воркерами; stale locks диагностируются и снимаются по правилам; locks общие для всех воркеров.

### EPIC R — Scheduler: выбор runnable узлов под N воркеров
- [ ] **W100-4** `skills/aidd-loop/runtime/scheduler.py`:
  - выбрать набор runnable узлов на N воркеров:
    - учитывать deps,
    - учитывать `locks`,
    - учитывать пересечения `expected_paths` (конфликт → не запускать параллельно; конфликт = общий top-level group или префикс),
    - сортировка: blocking → priority → plan order.
  **AC:** scheduler отдаёт набор независимых work items; не выдаёт конфликтующие по locks/paths.

- [ ] **W100-5** `skills/aidd-loop/runtime/loop_pack.py`:
  - уметь генерировать loop pack по конкретному work_item_id, а не только “следующий из NEXT_3”;
  - сохранять pack в per‑work‑item пути (Wave 87 уже подготовил).
  **AC:** можно собрать loop pack для любого узла DAG по id; pack содержит deps/locks/expected_paths/size_budget/tests для выбранного узла.

### EPIC S — Parallel loop-run (оркестрация воркеров)
- [ ] **W100-6** `skills/aidd-loop/runtime/loop_run.py`:
  - добавить режим `--parallel N`:
    - получить runnable узлы от scheduler,
    - claim locks,
    - запустить N воркеров (каждый с явным `--work-item <id>` / `scope_key`),
    - собирать stage results и принимать решения (blocked/done/continue) по каждому узлу.
  **AC:** parallel loop-run запускает N независимых узлов и корректно реагирует на BLOCKED/DONE по каждому; определён контракт artifact root (shared vs per-worktree) и сбор результатов.

- [ ] **W100-7** `skills/aidd-loop/runtime/worktree_manager.py` (или `tests/repo_tools/worktree.sh`):
  - подготовка isolated рабочих директорий на воркера:
    - `git worktree add` / отдельные ветки,
    - единый шаблон именования веток,
    - cleanup.
  **AC:** каждый воркер работает в изолированном worktree; определён способ записи артефактов (shared root или сбор из worktrees).

### EPIC T — Консолидация результатов обратно в основной tasklist
- [ ] **W100-8** `skills/aidd-flow-state/runtime/tasklist_consolidate.py`, `skills/aidd-flow-state/runtime/tasklist_normalize.py`:
  - на основе stage_result + review_pack + tests_log:
    - отметить `[x]` для завершённых узлов,
    - обновить `AIDD:NEXT_3` из DAG runnable,
    - добавить `AIDD:PROGRESS_LOG` записи,
    - перенос/дедуп handoff задач.
  **AC:** после параллельного прогона tasklist обновляется детерминированно; без дублей; NEXT_3 корректен; дедуп handoff по стабильному id.

- [ ] **W100-9** `skills/aidd-observability/runtime/aggregate_report.py`:
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

_Статус: plan. Цель — полностью внедрить file-based memory layer поверх текущего pack-first/RLM pipeline: отдельный semantic pack, append-only decision log, deterministic retrieval и gate-ready интеграция._
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

- [ ] **W101-15 (P1) Update full flow prompt script for Memory v2 (`docs/e2e/aidd_test_flow_prompt_ralph_script_full.txt`)** `docs/e2e/aidd_test_flow_prompt_ralph_script_full.txt`, `tests/repo_tools/smoke-workflow.sh`:
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

## Wave 102 — E2E Prompt Readiness WARN Tuning

_Статус: plan. Цель — ослабить E2E readiness gate только для scoped research WARN, не снижая fail-fast по ENV/contract mismatch._

### EPIC W2 — Scoped WARN policy in prompt contract

- [ ] **W102-1 (P0) Scoped research WARN for readiness gate (`R18/R12`)** `tests/repo_tools/e2e_prompt/profile_full.md`, `tests/repo_tools/e2e_prompt/profile_smoke.md`, `tests/repo_tools/test_e2e_prompt_contract.py`, `docs/e2e/aidd_test_flow_prompt_ralph_script_full.txt`, `docs/e2e/aidd_test_flow_prompt_ralph_script.txt`:
  - обновить readiness PASS rule: `research_status=reviewed|ok` или `research_status=warn` при scoped evidence;
  - добавить поле `research_warn_scope=<none|links_empty_non_blocking|invalid>` в contract `05_precondition_block.txt`;
  - расширить FAIL reason codes: добавить `research_warn_unscoped`;
  - зафиксировать классификацию:
    - scoped WARN -> `readiness_gate=PASS` + `WARN(readiness_gate_research_scoped)`;
    - unscoped WARN -> `readiness_gate=FAIL` + `reason_code=research_warn_unscoped`;
  - пересобирать root prompt outputs только через `python3 tests/repo_tools/build_e2e_prompts.py`.
  **AC:** FULL/SMOKE prompt fragments и generated scripts синхронизированы; readiness contract допускает только scoped research WARN; contract tests проходят.
  **Deps:** -
  **Regression/tests:** `python3 tests/repo_tools/build_e2e_prompts.py --check`, `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** S
  **Risk:** Low

- [ ] **W102-2 (P0) Plan-stage temporary soft gate for `rlm_status_pending` + usage telemetry** `skills/plan-new/runtime/research_check.py`, `tests/test_research_check.py`, `tests/repo_tools/smoke-workflow.sh`:
  - поддержать временный `warn-continue` режим только для `--expected-stage plan`, если после bounded finalize-probe остаётся `reason_code=rlm_status_pending`;
  - сохранить fail-fast для остальных reason codes (`rlm_nodes_missing`, `rlm_links_empty_warn`, invalid/missing artifacts);
  - добавить явный WARN-сигнал в stderr для операторской диагностики (policy marker + finalize probe outcome).
  **AC:** `research_check --expected-stage plan` не падает terminal только из-за `rlm_status_pending`; mandatory RLM artifacts продолжают валидироваться строго.
  **Deps:** W102-1
  **Regression/tests:** `python3 -m pytest -q tests/test_research_check.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W102-3 (P1) Replace temporary soft gate with deterministic readiness promotion path** `skills/researcher/runtime/research.py`, `skills/aidd-rlm/runtime/rlm_finalize.py`, `skills/aidd-core/runtime/research_guard.py`, `tests/test_research_command.py`, `tests/test_research_check.py`:
  - убрать необходимость soft-continue за счёт детерминированного перехода `pending -> ready|warn(scoped)` в bounded auto-recovery;
  - нормализовать reason codes и next-action hints между researcher/research_guard/research_check;
  - обеспечить стабильный `rlm_status` в pack/worklist при повторных прогонах.
  **AC:** pipeline сходится без временного plan-softening в репрезентативных сценариях; `rlm_status_pending` остаётся только при реальных hard blockers.
  **Deps:** W102-2
  **Regression/tests:** `python3 -m pytest -q tests/test_research_command.py tests/test_research_check.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W102-4 (P1) Readiness gate/report alignment for `research_not_ready` diagnostics** `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/e2e_prompt/profile_full.md`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - фиксировать отдельные подпpичины `research_not_ready` (`pending`, `nodes_missing`, `links_empty_unscoped`, `pack_missing`) в precondition artifacts;
  - синхронизовать readiness diagnostics между stage-return и `05_precondition_block.txt`;
  - добавить проверку, что временный plan-soft mode не маскирует contract/env incidents.
  **AC:** оператор видит точную подпpичину `research_not_ready`; prompt-contract tests покрывают расхождения report vs stage-return.
  **Deps:** W102-3
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** Medium

## Wave 104 — Always-soft research gates + QA convergence recovery

_Статус: plan. Цель — временно исключить terminal-block по research warn/pending на шагах 5.2/7, сохранив fail-fast для ENV/contract/runtime-path и восстановить строгие проверки после стабилизации._

- [ ] **W104-1 (P0) Always-soft rollout для шагов 5.2/7 (runtime + prompt + tests)** `skills/aidd-core/runtime/research_guard.py`, `hooks/gate_workflow.py`, `skills/aidd-loop/runtime/loop_run_parts/core.py`, `skills/aidd-loop/runtime/loop_block_policy.py`, `templates/aidd/config/gates.json`, `tests/repo_tools/e2e_prompt/profile_{full,smoke}.md`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - включить `researcher.downstream_gate_mode=always_soft` и default `loop.blocked_policy=ralph`;
  - перевести `rlm_links_empty_warn|rlm_status_pending` в non-terminal soft path при minimal baseline;
  - добавить loop telemetry `research_gate_softened/reason/policy`.
  **AC:** шаг 5.2 и шаг 7 не завершаются terminal fail только из-за research warn/pending при baseline; ENV/contract/runtime-path причины остаются terminal.
  **Deps:** -
  **Regression/tests:** `python3 tests/repo_tools/build_e2e_prompts.py --check`, `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py tests/test_research_check.py tests/test_gate_researcher.py tests/test_gate_workflow.py tests/test_loop_run.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W104-2 (P0) Research root-cause fix (`no_symbols/no_matches`, links build stability, finalize convergence)** `skills/researcher/runtime/research.py`, `skills/aidd-rlm/runtime/rlm_links_build.py`, `skills/aidd-rlm/runtime/rlm_finalize.py`, `skills/aidd-core/runtime/research_guard.py`, `tests/test_research_command.py`, `tests/test_research_check.py`:
  - устранить причины пустых links в валидных code scopes;
  - стабилизировать bounded finalize и детерминированный переход `pending -> ready|warn`;
  - сократить ложные `pending` после авто-recovery.
  **AC:** `rlm_links_empty_warn|rlm_status_pending` остаются только в репрезентативных hard-case сценариях; auto-finalize converges без soft override в большинстве прогонов.
  **Deps:** W104-1
  **Regression/tests:** `python3 -m pytest -q tests/test_research_command.py tests/test_research_check.py tests/test_gate_workflow.py`.
  **Effort:** L
  **Risk:** High

- [ ] **W104-3 (P1) Restore strict research gates после стабилизации** `templates/aidd/config/gates.json`, `skills/aidd-core/runtime/research_guard.py`, `skills/aidd-loop/runtime/loop_block_policy.py`, `tests/repo_tools/e2e_prompt/profile_{full,smoke}.md`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - вернуть strict-default policy (`downstream_gate_mode=strict` и strict readiness contract);
  - оставить runtime override через CLI/env для controlled rollout;
  - добавить strict-profile regression в prompt/runtime tests.
  **AC:** strict режим воспроизводимо блокирует warn/pending при отсутствии explicit soft override; soft rollout остаётся управляемым feature-flag.
  **Deps:** W104-2
  **Regression/tests:** `python3 tests/repo_tools/build_e2e_prompts.py --check`, `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py tests/test_research_check.py tests/test_loop_run.py`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W104-4 (P0) QA convergence hardening (phase-1/phase-2)** `skills/qa/runtime/qa_parts/core.py`, `skills/aidd-docio/runtime/actions_apply.py`, `hooks/gate_workflow.py`, `skills/qa/SKILL.md`, `agents/qa.md`, `tests/test_qa_agent.py`, `tests/test_qa_exit_code.py`, `tests/test_loop_step.py`:
  - phase-1: fail-fast на `preflight_missing`/workflow-root mismatch и запрет repeated guessed retries;
  - phase-2: prevalidate actions payload до apply с unified reason code `contract_mismatch_actions_shape`, early BLOCK и canonical next action;
  - обеспечить детерминированный terminal payload в одном run без watchdog no-result цикла.
  **AC:** QA run завершает top-level result до watchdog budget; repeated stop-hook cycle без terminal payload не воспроизводится; next action для preflight missing = `/feature-dev-aidd:tasks-new <ticket>`.
  **Deps:** W104-1
  **Regression/tests:** `python3 -m pytest -q tests/test_qa_agent.py tests/test_qa_exit_code.py tests/test_loop_step.py tests/test_gate_workflow_preflight_contract.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W104-5 (P0) Stage actions terminalization + anti-drift guard (implement/review/qa)** `skills/aidd-core/runtime/stage_actions_run.py`, `skills/aidd-docio/runtime/actions_validate.py`, `skills/aidd-docio/runtime/actions_apply.py`, `skills/implement/SKILL.md`, `skills/review/SKILL.md`, `skills/qa/SKILL.md`, `tests/test_stage_actions_run.py`, `tests/test_wave93_validators.py`, `tests/test_prompt_lint.py`, `tests/test_gate_workflow_preflight_contract.py`:
  - при invalid `AIDD:ACTIONS` возвращать единый terminal payload с `reason_code=contract_mismatch_actions_shape` без guessed/manual recovery;
  - запретить в stage-prompts direct/non-canonical `stage_result.py` handoff как primary path;
  - зафиксировать prompt-lint tripwire на `python3 skills/.../stage_result.py` и невалидные `--result` значения.
  **AC:** invalid actions shape завершает run одним canonical blocked-result; manual/non-canonical stage-result path не предлагается как primary next action.
  **Deps:** W104-4
  **Regression/tests:** `python3 -m pytest -q tests/test_stage_actions_run.py tests/test_wave93_validators.py tests/test_gate_workflow_preflight_contract.py tests/test_prompt_lint.py`.
  **Effort:** M
  **Risk:** High

## Wave 105 — Loop review-pack recovery + 1h iteration timeout

_Статус: plan. Цель — точечно смягчить loop только для `review_pack_missing|review_pack_stale` в `ralph`, поднять timeout итерации до 1 часа и зафиксировать контракт в prompt/tests._

- [ ] **W105-1 (P0) Ralph targeted recovery for review-pack reasons** `skills/aidd-loop/runtime/loop_block_policy.py`, `templates/aidd/config/gates.json`, `tests/test_loop_run.py`:
  - перевести `review_pack_missing|review_pack_stale` в `recoverable_retry` только для `blocked_policy=ralph`;
  - сохранить terminal поведение для `strict` и для ENV/contract/runtime-path hard blockers.
  **AC:** в `ralph` review-pack причины получают bounded retry; в `strict` остаются terminal blocked без recoverable path.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_run.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W105-2 (P0) Loop iteration timeout 1h contract** `skills/aidd-loop/runtime/loop_run_parts/core.py`, `tests/repo_tools/e2e_prompt/profile_full.md`, `docs/e2e/aidd_test_flow_prompt_ralph_script_full.txt`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - установить default `DEFAULT_LOOP_STEP_TIMEOUT_SECONDS=3600` при сохранении `DEFAULT_STAGE_BUDGET_SECONDS=3600`;
  - зафиксировать в full-flow prompt явные флаги `--step-timeout-seconds $LOOP_STEP_TIMEOUT_SECONDS` и `--stage-budget-seconds $LOOP_STAGE_BUDGET_SECONDS`.
  **AC:** runtime default и full prompt/script согласованы на 3600s; prompt-contract тесты проверяют наличие timeout flags.
  **Deps:** W105-1
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py tests/test_loop_run.py`.
  **Effort:** S
  **Risk:** Low

- [ ] **W105-3 (P1) Review-pack recovery path hardening** `skills/aidd-loop/runtime/loop_run_parts/core.py`, `tests/test_loop_run.py`:
  - добавить детерминированный recovery path `retry_review_pack` для stage=`review` при review-pack recoverable reason;
  - исключить деградацию в `handoff_to_implement` для этой причины.
  **AC:** telemetry содержит `recovery_path=retry_review_pack`; bounded retry не переключает stage в implement.
  **Deps:** W105-1
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_run.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W105-4 (P1) Regression coverage for targeted relax + timeout contract** `tests/test_loop_run.py`, `tests/repo_tools/test_e2e_prompt_contract.py`, `tests/repo_tools/ci-lint.sh`:
  - покрыть кейсы: `ralph + review_pack_missing` recoverable, `strict + review_pack_missing` terminal, default step-timeout `3600`, наличие timeout flags в full prompt;
  - закрепить через CI-repro entrypoint.
  **AC:** unit + prompt-contract тесты стабильно ловят регрессии по policy/timeouts.
  **Deps:** W105-2, W105-3
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_run.py tests/repo_tools/test_e2e_prompt_contract.py`, `tests/repo_tools/ci-lint.sh`.
  **Effort:** S
  **Risk:** Low

- [ ] **W105-5 (P0) Ralph recovery for `no_tests_hard` with bounded test-derive retry** `skills/aidd-loop/runtime/loop_block_policy.py`, `skills/aidd-loop/runtime/loop_run_parts/core.py`, `skills/aidd-loop/runtime/loop_step_parts/core.py`, `skills/aidd-flow-state/runtime/tasks_derive.py`, `templates/aidd/config/gates.json`, `tests/test_loop_run.py`, `tests/test_loop_step.py`:
  - для `blocked_policy=ralph` и `reason_code=no_tests_hard` запускать bounded recovery path `derive_tests_then_retry_review`, если tasklist подтверждает executable test entries;
  - если executable entries не подтверждены — сохранять terminal blocked с явным `ralph_recoverable_not_exercised_reason`;
  - strict policy не ослаблять.
  **AC:** loop не падает terminal на первом `no_tests_hard` при наличии исполняемых test entries; strict mode поведение не меняется.
  **Deps:** W105-1, W105-2
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_run.py tests/test_loop_step.py`.
  **Effort:** M
  **Risk:** High

## Wave 106 — TST-001 WARN cleanup (plugin-only stabilization)

_Статус: plan. Цель — убрать ложные WARN/telemetry noise без ослабления ENV/contract fail-fast._

- [ ] **W106-1 (P1) Scope fallback confinement for stage-result lookup** `skills/aidd-loop/runtime/loop_step_stage_result.py`, `skills/aidd-loop/runtime/loop_step_parts/core.py`, `skills/aidd-loop/runtime/loop_run_parts/core.py`, `tests/test_loop_step.py`, `tests/test_loop_run.py`:
  - ужесточить fallback selection: preferred scope authoritative; cross-scope fallback только с `scope_drift_recoverable` marker;
  - убрать повторяющийся `scope_key_mismatch_warn` noise при стабильном scope.
  **AC:** повторяемый fallback `iteration_id_I2 -> iteration_id_I1` без recoverable diagnostics не воспроизводится.
  **Deps:** W105-5
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_step.py tests/test_loop_run.py`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W106-2 (P1) Output contract signal precision (`read_log_missing`, `read_order_missing_loop_pack`)** `skills/aidd-loop/runtime/output_contract.py`, `skills/aidd-loop/runtime/loop_step_parts/core.py`, `tests/test_output_contract.py`, `tests/test_loop_step.py`, `tests/test_gate_workflow_preflight_contract.py`:
  - разделить реальные нарушения контракта и telemetry lag;
  - не поднимать `output_contract_warn` при валидном stream-evidence и корректном loop-pack read order.
  **AC:** WARN остаётся только при реальном contract gap, а не из-за неполного telemetry flush.
  **Deps:** W106-1
  **Regression/tests:** `python3 -m pytest -q tests/test_output_contract.py tests/test_loop_step.py tests/test_gate_workflow_preflight_contract.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W106-3 (P0) Review-spec report/narrative convergence diagnostics** `skills/aidd-core/runtime/prd_review.py`, `tests/test_prd_review_agent.py`, `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/e2e_prompt/profile_full.md`, `tests/repo_tools/e2e_prompt/profile_smoke.md`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - синхронизовать narrative с report summary и явно маркировать `review_spec_report_mismatch` только при фактическом расхождении;
  - в audit runner закрепить приоритет report payload для recovery decision.
  **AC:** mismatch детерминированно диагностируется; recovery-решения всегда берутся из report payload.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_prd_review_agent.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** S
  **Risk:** Low

- [ ] **W106-4 (P0) Tasklist hygiene WARN normalization (non-terminal by design)** `skills/aidd-flow-state/runtime/tasklist_check.py`, `skills/aidd-flow-state/runtime/tasklist_normalize.py`, `skills/tasks-new/SKILL.md`, `tests/test_tasklist_check.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - нормализовать и дедуплицировать hygiene WARN (`max_loc`, `expected_paths`, `NEXT_3 deps`, `PROGRESS_LOG format`);
  - сохранить terminal только для реально неисполняемого `AIDD:TEST_EXECUTION`, без отката недавнего fix на multiline `tasks`.
  - явно закрепить non-terminal правило: при `tasks_key_present=1` и `tasks_list_count>0` классификация остаётся `WARN|INFO` без escalation в blocker, даже при parser mismatch telemetry.
  **AC:** `tasks-new` не блокируется из-за hygiene-only WARN; `missing tasks` остаётся ошибкой только при реальном отсутствии задач; `tasklist_schema_parser_mismatch_recoverable` не повышается в terminal blocker при наличии исполняемых task entries.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_tasklist_check.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** S
  **Risk:** Low

- [ ] **W106-5 (P1) PRD section parsing + cache-version hardening** `skills/aidd-flow-state/runtime/prd_check.py`, `skills/aidd-core/runtime/prd_review.py`, `tests/test_prd_ready_check.py`, `tests/test_prd_review_agent.py`:
  - завершать секции `AIDD:*` на любом markdown heading (`#{1,6}`), не только `##`;
  - versioned cache для `prd-check` (`cache_version`) и ignore legacy cache payload без актуальной версии.
  **AC:** nested headings не ломают readiness parsing; stale cache без `cache_version` не bypass-ит актуальную проверку.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_prd_ready_check.py tests/test_prd_review_agent.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W106-6 (P1) Canonical `aidd/*` workspace layout enforcement (no root migration)** `skills/aidd-core/runtime/runtime.py`, `hooks/hooklib.py`, `hooks/context_gc/pretooluse_guard.py`, `tests/test_resources.py`, `tests/test_context_gc.py`, `tests/test_hook_rw_policy.py`, `tests/repo_tools/smoke-workflow.sh`, `tests/repo_tools/e2e_prompt/profile_full.md`, `tests/repo_tools/e2e_prompt/profile_smoke.md`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - enforce canonical runtime artifacts only under `aidd/docs/**`, `aidd/reports/**`, `aidd/config/**`, `aidd/.cache/**`;
  - remove auto-migration of root paths (`docs/**|reports/**|config/**|.cache/**`) into `aidd/*`;
  - when `aidd/docs` is missing, return deterministic bootstrap error (`/feature-dev-aidd:aidd-init`) without mutating workspace root;
  - keep root-level non-canonical paths untouched by runtime; block root-level writes when `aidd/` exists.
  **AC:** full/smoke flows do not mutate root-level non-canonical artifacts; runtime and hooks resolve only canonical `aidd/*` paths.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_resources.py tests/test_context_gc.py tests/test_hook_rw_policy.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W106-7 (P0) Silent-stall determinism for loop/qa runners** `skills/aidd-loop/runtime/loop_run_parts/core.py`, `skills/qa/runtime/qa_parts/core.py`, `tests/test_loop_run.py`, `tests/test_qa_agent.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - стабилизировать liveness finalization в loop/qa, чтобы процесс не оставался "живым без top-level result" до budget kill;
  - возвращать детерминированный terminal payload с `reason_code=silent_stall` при подтверждённой стагнации main+stream;
  - синхронизовать классификацию watchdog/silent-stall в runtime и e2e contract.
  **AC:** на synthetic stall кейсах нет сценария "процесс жив >20m без top-level result" без явного terminal payload.
  **Deps:** W104-4
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_run.py tests/test_qa_agent.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W106-8 (P0) QA status contract hardening (report ↔ top-level parity)** `skills/qa/runtime/qa_parts/core.py`, `skills/qa/runtime/qa.py`, `tests/test_qa_agent.py`, `tests/test_qa_exit_code.py`:
  - зафиксировать strict parity между `aidd/reports/qa/<ticket>.json` status и top-level stage status;
  - запретить `success` при `qa report status=BLOCKED`, оставить только `blocked|warn`;
  - документировать таблицу status mapping в runtime diagnostics.
  **AC:** `report=BLOCKED => stage status in {blocked,warn}`; `success` возможен только при `report=PASS`.
  **Deps:** W104-5
  **Regression/tests:** `python3 -m pytest -q tests/test_qa_agent.py tests/test_qa_exit_code.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W106-9 (P1) Canonical orchestration guard against internal manual recovery paths** `skills/qa/SKILL.md`, `skills/aidd-loop/SKILL.md`, `tests/test_prompt_lint.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - запретить рекомендации и primary recovery path с direct internal preflight/stage-result writes;
  - добавить prompt-lint tripwire на non-canonical ручной handoff внутри QA/loop orchestrations;
  - оставить только canonical stage-chain next actions в top-level stage-return.
  **AC:** prompt-lint ловит non-canonical recovery hints; e2e contract tests падают на manual stage-result path в primary action.
  **Deps:** W104-5
  **Regression/tests:** `python3 -m pytest -q tests/test_prompt_lint.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W106-10 (P1) Write-safety classifier baseline awareness for root non-canonical paths** `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/test_e2e_prompt_contract.py`, `tests/repo_tools/test_audit_runner.py`:
  - отличать pre-existing root `docs|reports|config|.cache` от newly-created/modified during run;
  - при отсутствии delta классифицировать как `INFO(preexisting_noncanonical_root)`, не как WARN;
  - поднимать WARN только при фактической мутации root non-canonical paths во время прогона.
  **AC:** pre-existing неизменённый root path больше не приводит к WARN; delta/mutation остаётся WARN.
  **Deps:** W106-6
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_audit_runner.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W106-11 (P1) Stream-path telemetry completeness for stall classification** `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/e2e_prompt/profile_full.md`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - сделать fallback discovery обязательным при `stream_paths_missing` и пустом валидном наборе primary extraction;
  - фиксировать `stream_path_not_emitted_by_cli` как non-terminal noise при валидном top-level result;
  - синхронизовать liveness классификацию между prompt contract и audit runner.
  **AC:** ложный stall из-за пустого primary stream-path extraction не воспроизводится при живом stream/fallback evidence.
  **Deps:** W106-7
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** S
  **Risk:** Medium
