# Product Backlog

> INTERNAL/DEV-ONLY: engineering wave planning and execution tracker.

_Revision note (2026-04-02): backlog нормализован в пять активных wave. Дубликаты, historical incident notes и superseded blocks удалены; backlog отражает только исполнимые программы работ, а крупные platform adaptations вынесены в отдельные low-priority wave._

## Wave 120 — Core Flow Stabilization (2026-04-02)

_Статус: plan. Основание — high-priority стабилизация полного e2e flow, seed stages, loop orchestration, canonical stage contract и research gate._

- [ ] **W120-1 (P0) Seed-stage convergence and terminal result emission** `skills/implement/runtime/implement_run.py`, `skills/review/runtime/review_run.py`, `skills/qa/runtime/qa_parts/core.py`, `skills/aidd-loop/runtime/loop_run_parts/core.py`, `tests/test_implement_agent.py`, `tests/test_review_run.py`, `tests/test_qa_agent.py`, `tests/test_loop_run.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - ввести единый convergence guard для seed runs, чтобы живой run не дожидался budget kill без terminal payload;
  - ограничить retry для повторяющихся `preflight_missing` и `contract_mismatch` детерминированным числом попыток;
  - гарантировать canonical top-level result/event до `exit_code=143` и синхронизовать watchdog attribution.
  **AC:** implement/review/qa seed runs не завершаются `result_count=0` при валидном init; terminal payload всегда присутствует до budget termination.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_implement_agent.py tests/test_review_run.py tests/test_qa_agent.py tests/test_loop_run.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W120-2 (P0) Canonical stage-result, preflight, and actions contract** `skills/aidd-core/runtime/stage_actions_run.py`, `skills/aidd-flow-state/runtime/stage_result.py`, `skills/aidd-docio/runtime/actions_validate.py`, `skills/aidd-docio/runtime/actions_apply.py`, `tests/test_stage_actions_run.py`, `tests/test_gate_workflow_preflight_contract.py`, `tests/test_wave93_validators.py`, `tests/test_prompt_lint.py`:
  - закрепить canonical `aidd.stage_result.v1` shape для preflight и terminal artifacts;
  - завершать invalid `AIDD:ACTIONS` одним canonical blocked-result без guessed/manual recovery;
  - запретить manual write path для `stage.*.result.json` как primary recovery route.
  **AC:** preflight и terminal stage results всегда имеют canonical contract shape; manual stage-result write не предлагается и не исполняется как основной путь.
  **Deps:** W120-1
  **Regression/tests:** `python3 -m pytest -q tests/test_stage_actions_run.py tests/test_gate_workflow_preflight_contract.py tests/test_wave93_validators.py tests/test_prompt_lint.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W120-3 (P0) Implement, review, and QA verdict mapping hardening** `skills/implement/runtime/implement_run.py`, `skills/review/runtime/review_run.py`, `skills/qa/runtime/qa.py`, `skills/qa/runtime/qa_parts/core.py`, `skills/aidd-flow-state/runtime/stage_result.py`, `tests/test_review_run.py`, `tests/test_review_agent.py`, `tests/test_qa_agent.py`, `tests/test_qa_exit_code.py`:
  - нормализовать user-facing verdict -> canonical result mapping для implement/review/qa;
  - исключить `success` narrative при blocked report/stage result;
  - возвращать единый deterministic terminal payload для repeated `command_not_found`, `no_tests_hard`, blocked findings и report parity failures.
  **AC:** review и QA narrative не противоречат canonical stage/report status; non-canonical `--result` values и contradictory pass verdicts не воспроизводятся.
  **Deps:** W120-2
  **Regression/tests:** `python3 -m pytest -q tests/test_review_run.py tests/test_review_agent.py tests/test_qa_agent.py tests/test_qa_exit_code.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W120-4 (P0) Canonical scope authority and stage-result fallback selection** `skills/aidd-loop/runtime/loop_step_stage_result.py`, `skills/aidd-loop/runtime/loop_step_parts/core.py`, `skills/aidd-loop/runtime/loop_run_parts/core.py`, `tests/test_loop_step.py`, `tests/test_loop_run.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - ввести один authoritative resolver для `scope_key` и `work_item_key`;
  - разрешать cross-scope fallback только при явном recoverable marker и полной diagnostics surface;
  - убрать неоднозначные scope transitions и повторяющийся mismatch telemetry noise.
  **AC:** одна итерация использует один canonical scope namespace; fallback без recoverable diagnostics не выбирает чужой scope.
  **Deps:** W120-2
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_step.py tests/test_loop_run.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W120-5 (P0) Loop timeout and recoverable-retry policy** `skills/aidd-loop/runtime/loop_block_policy.py`, `skills/aidd-loop/runtime/loop_run_parts/core.py`, `skills/aidd-loop/runtime/loop_step_parts/core.py`, `skills/aidd-flow-state/runtime/tasks_derive.py`, `templates/aidd/config/gates.json`, `tests/test_loop_run.py`, `tests/test_loop_step.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - закрепить timeout contract для loop-step и stage budgets на runtime и prompt surfaces;
  - нормализовать recoverable retry policy для `ralph` без ослабления strict mode;
  - ограничить auto-recovery для review-pack и `no_tests_hard` явными policy conditions и telemetry.
  **AC:** timeout flags и runtime defaults согласованы; `ralph` выполняет только разрешённые bounded retries, а strict mode сохраняет terminal behavior.
  **Deps:** W120-4
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_run.py tests/test_loop_step.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W120-6 (P0) Research gate normalization and convergence path** `skills/researcher/runtime/research.py`, `skills/aidd-rlm/runtime/rlm_links_build.py`, `skills/aidd-rlm/runtime/rlm_finalize.py`, `skills/aidd-core/runtime/research_guard.py`, `skills/plan-new/runtime/research_check.py`, `templates/aidd/config/gates.json`, `tests/test_research_command.py`, `tests/test_research_check.py`, `tests/test_gate_workflow.py`, `tests/test_loop_run.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - сократить ложные `pending` и `links_empty` через bounded finalize convergence и root-cause fixes;
  - сделать readiness diagnostics однозначными для `warn`, `pending`, `missing artifacts` и `strict`/`soft` policy;
  - подготовить controlled path от temporary soft gating к строгому режиму после стабилизации.
  **AC:** research gate различает recoverable и hard-blocking причины без ambiguous telemetry; majority-case runs сходятся без временных soft overrides.
  **Deps:** W120-1
  **Regression/tests:** `python3 -m pytest -q tests/test_research_command.py tests/test_research_check.py tests/test_gate_workflow.py tests/test_loop_run.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** L
  **Risk:** High

- [ ] **W120-7 (P0) Canonical workspace layout enforcement** `skills/aidd-core/runtime/runtime.py`, `hooks/hooklib.py`, `hooks/context_gc/pretooluse_guard.py`, `tests/test_resources.py`, `tests/test_context_gc.py`, `tests/test_hook_rw_policy.py`, `tests/repo_tools/test_e2e_prompt_contract.py`, `tests/repo_tools/smoke-workflow.sh`:
  - разрешить runtime writes только в canonical `aidd/docs/**`, `aidd/reports/**`, `aidd/config/**`, `aidd/.cache/**`;
  - убрать auto-migration root paths и вернуть deterministic bootstrap error, если workspace не инициализирован;
  - синхронизовать hooks и runtime path resolution на одном workspace contract.
  **AC:** full/smoke flows не мутируют root-level non-canonical paths; runtime и hooks используют только canonical `aidd/*` layout.
  **Deps:** W120-2
  **Regression/tests:** `python3 -m pytest -q tests/test_resources.py tests/test_context_gc.py tests/test_hook_rw_policy.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** Medium

## Wave 121 — Prompt, Audit, and Tasklist Hygiene (2026-04-02)

_Статус: plan. Основание — P1 cleanup prompt surfaces, audit classification, replay coverage и operator-facing deterministic guidance без вмешательства в core runtime semantics._

- [ ] **W121-1 (P1) `review-spec` structured payload as source-of-truth** `skills/aidd-core/runtime/prd_review.py`, `skills/aidd-core/runtime/prd_review_section.py`, `tests/test_prd_review_agent.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - вычислять top-level narrative только из structured report payload;
  - стабилизировать report trimming без изменения recommended status и findings semantics;
  - убрать расхождения между report, summary и downstream recovery decisions.
  **AC:** `review-spec` не воспроизводит narrative/report mismatch; recovery path всегда определяется structured payload.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_prd_review_agent.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W121-2 (P1) Canonical prompt orchestration and derive routing** `skills/researcher/SKILL.md`, `skills/plan-new/SKILL.md`, `skills/tasks-new/SKILL.md`, `skills/implement/SKILL.md`, `skills/review/SKILL.md`, `skills/qa/SKILL.md`, `agents/researcher.md`, `agents/planner.md`, `agents/tasklist-refiner.md`, `agents/implementer.md`, `tests/test_prompt_lint.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - убрать non-canonical runtime hints, legacy aliases и source-less derive guidance из stage prompts;
  - закрепить canonical derive routing по stage ownership и canonical CLI arguments only;
  - убрать generic nested recovery handoffs, которые уводят в drift paths или manual internals.
  **AC:** top-level prompt surfaces не содержат non-canonical runtime paths, legacy aliases или derive without explicit canonical source.
  **Deps:** W120-2
  **Regression/tests:** `python3 -m pytest -q tests/test_prompt_lint.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W121-3 (P1) Audit runner liveness, stream-path, and termination attribution** `tests/repo_tools/aidd_stage_launcher.py`, `tests/repo_tools/aidd_stream_paths.py`, `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/test_aidd_stage_launcher.py`, `tests/repo_tools/test_aidd_audit_runner.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - унифицировать stream-path extraction и fallback discovery для `stream_path_not_emitted_by_cli`;
  - разделить `watchdog terminate`, `external terminate`, `silent stall`, `active stream` и parser noise;
  - исключить ложные terminal transitions при активном stream и неполной telemetry surface.
  **AC:** audit runner детерминированно классифицирует `exit_code=143` и stream-path anomalies без смешения terminal status и telemetry noise.
  **Deps:** W120-1
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_aidd_stage_launcher.py tests/repo_tools/test_aidd_audit_runner.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W121-4 (P1) Write-safety and readiness telemetry normalization** `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/test_aidd_audit_runner.py`, `tests/repo_tools/test_audit_runner.py`, `tests/repo_tools/test_e2e_prompt_contract.py`, `tests/repo_tools/e2e_prompt/profile_full.md`:
  - различать pre-existing layout noise, runtime write-safety breach и post-recovery superseded telemetry;
  - убрать конфликтующие readiness narratives после успешного downstream recovery;
  - сохранять только actionable WARN/FAIL classification в итоговых step summaries.
  **AC:** pre-existing root paths и superseded readiness markers не поднимают ложные WARN/NOT VERIFIED; real runtime mutations остаются видимыми.
  **Deps:** W120-7
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_aidd_audit_runner.py tests/repo_tools/test_audit_runner.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W121-5 (P1) Replay fixtures, tasklist edge cases, and PRD parser hardening** `tests/fixtures/audit_tst001_*/*`, `skills/tasks-new/runtime/tasks_new.py`, `skills/aidd-flow-state/runtime/tasklist_check.py`, `skills/aidd-flow-state/runtime/tasklist_normalize.py`, `skills/aidd-flow-state/runtime/prd_check.py`, `tests/test_tasks_new.py`, `tests/test_tasklist_check.py`, `tests/test_prd_ready_check.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - оформить replay fixtures для критичных TST-class incidents и связать их с CI-facing contract tests;
  - стабилизировать nested-skill/tasklist parser edge cases так, чтобы hygiene-only issues не становились blocker;
  - ужесточить PRD section parsing и cache invalidation без legacy bypass поведения.
  **AC:** replay fixtures воспроизводят audit incidents детерминированно; tasks-new и PRD checks не дают ложных blockers на parser-only cases.
  **Deps:** W121-3
  **Regression/tests:** `python3 -m pytest -q tests/test_tasks_new.py tests/test_tasklist_check.py tests/test_prd_ready_check.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** Medium

## Wave 122 — Memory Platform (2026-04-02)

_Статус: plan. Основание — low-priority cross-cutting развитие memory layer. Волна изолирована от текущей стабилизации runtime и не должна конкурировать с Core Flow fixes._
_Planned refs: пути в задачах этой волны могут ссылаться на будущие (ещё не созданные) файлы._

- [ ] **W122-1 (P2) Memory foundation, schemas, and bootstrap wiring** `skills/aidd-memory/SKILL.md`, `skills/aidd-memory/runtime/*.py`, `skills/aidd-core/runtime/schemas/aidd/*.json`, `.claude-plugin/plugin.json`, `skills/aidd-init/runtime/init.py`, `templates/aidd/config/conventions.json`, `templates/aidd/config/gates.json`, `templates/aidd/reports/memory/.gitkeep`, `tests/test_memory_verify.py`, `tests/test_init_aidd.py`:
  - ввести shared memory skill, runtime inventory и schema contract для semantic and decision artifacts;
  - подготовить bootstrap/config wiring для новых workspace;
  - закрепить validator surface и budgets как canonical part of memory layer.
  **AC:** memory runtime и schemas доступны как canonical plugin surface; новый workspace получает required config и directories из коробки.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_memory_verify.py tests/test_init_aidd.py`, `tests/repo_tools/ci-lint.sh`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W122-2 (P2) Semantic and decision artifact generation** `skills/aidd-memory/runtime/memory_extract.py`, `skills/aidd-memory/runtime/decision_append.py`, `skills/aidd-memory/runtime/memory_pack.py`, `skills/researcher/runtime/research.py`, `skills/aidd-docio/runtime/actions_validate.py`, `skills/aidd-docio/runtime/actions_apply.py`, `tests/test_memory_extract.py`, `tests/test_memory_decisions.py`, `tests/test_wave93_validators.py`, `tests/test_research_command.py`:
  - генерировать semantic pack и append-only decisions log с deterministic pack assembly;
  - запускать semantic extraction после research readiness;
  - разрешить decision writes только через validated actions flow.
  **AC:** semantic и decisions artifacts генерируются детерминированно, а decision writes проходят только через validated path.
  **Deps:** W122-1
  **Regression/tests:** `python3 -m pytest -q tests/test_memory_extract.py tests/test_memory_decisions.py tests/test_wave93_validators.py tests/test_research_command.py`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W122-3 (P2) Runtime integration into read path, guards, context, and status** `skills/aidd-core/runtime/research_guard.py`, `skills/aidd-loop/runtime/preflight_prepare.py`, `skills/aidd-loop/runtime/output_contract.py`, `hooks/context_gc/pretooluse_guard.py`, `hooks/context_gc/working_set_builder.py`, `skills/status/runtime/index_sync.py`, `skills/aidd-policy/references/read-policy.md`, `skills/aidd-core/templates/context-pack.template.md`, `skills/aidd-core/templates/index.schema.json`, `tests/test_preflight_prepare.py`, `tests/test_output_contract.py`, `tests/test_status.py`, `tests/test_wave95_policy_guards.py`, `tests/test_gate_workflow.py`:
  - интегрировать memory artifacts в read order, guards, working set и status/index discovery;
  - добавить configurable readiness checks для memory completeness;
  - сохранить bounded excerpts и deterministic context budgets.
  **AC:** runtime может читать memory artifacts через canonical read path; guards/status/context не расходятся с memory contract.
  **Deps:** W122-2
  **Regression/tests:** `python3 -m pytest -q tests/test_preflight_prepare.py tests/test_output_contract.py tests/test_status.py tests/test_wave95_policy_guards.py tests/test_gate_workflow.py`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W122-4 (P2) Memory docs, rollout, and regression coverage** `AGENTS.md`, `README.md`, `README.en.md`, `templates/aidd/AGENTS.md`, `CHANGELOG.md`, `docs/memory-v2-rfc.md`, `docs/e2e/aidd_test_flow_prompt_ralph_script_full.txt`, `tests/test_memory_*.py`, `tests/repo_tools/smoke-workflow.sh`, `tests/repo_tools/ci-lint.sh`:
  - оформить operator docs и rollout policy для memory layer без legacy backfill narrative;
  - обновить full-flow prompt script под canonical memory read chain;
  - собрать regression suite для generation, reads, writes и gates.
  **AC:** docs и tests описывают memory platform как согласованный low-priority roadmap; regression suite покрывает memory lifecycle end to end.
  **Deps:** W122-3
  **Regression/tests:** `python3 -m pytest -q tests/test_memory_*.py`, `tests/repo_tools/smoke-workflow.sh`, `tests/repo_tools/ci-lint.sh`.
  **Effort:** M
  **Risk:** Low

## Wave 123 — DAG / Parallel Loop Roadmap (2026-04-02)

_Статус: plan. Основание — low-priority future architecture backlog для task graph, scheduling и parallel loop execution. Волна сознательно отделена от текущей стабилизации flow._
_Planned refs: пути в задачах этой волны могут ссылаться на будущие (ещё не созданные) файлы._

- [ ] **W123-1 (P2) Task graph and validation** `skills/aidd-flow-state/runtime/task_graph.py`, `skills/aidd-flow-state/runtime/taskgraph_check.py`, `aidd/reports/taskgraph/<ticket>.json`, `tests/test_scheduler.py`:
  - построить DAG из tasklist с deterministic node ids, deps, locks, blocking metadata и runnable state;
  - добавить topology validation для cycles, self-deps и invalid references;
  - сохранить machine-readable task graph artifact для downstream scheduler.
  **AC:** tasklist детерминированно преобразуется в DAG; invalid graph conditions ловятся до запуска parallel orchestration.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_scheduler.py`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W123-2 (P2) Claims, scheduler, and per-work-item loop packs** `skills/aidd-loop/runtime/work_item_claim.py`, `skills/aidd-loop/runtime/scheduler.py`, `skills/aidd-loop/runtime/loop_pack.py`, `tests/test_scheduler.py`, `tests/test_parallel_loop_run.py`:
  - реализовать claim/release/renew lock protocol для shared work items;
  - выбирать runnable set с учётом deps, locks и path conflicts;
  - собирать pack по конкретному work item, а не только по текущему serial handoff.
  **AC:** scheduler выдаёт только независимые runnable items; locks и pack generation согласованы по одному work-item contract.
  **Deps:** W123-1
  **Regression/tests:** `python3 -m pytest -q tests/test_scheduler.py tests/test_parallel_loop_run.py`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W123-3 (P2) Parallel runner and isolated worktrees** `skills/aidd-loop/runtime/loop_run.py`, `skills/aidd-loop/runtime/worktree_manager.py`, `tests/test_parallel_loop_run.py`, `tests/repo_tools/parallel-loop-regression.sh`:
  - добавить `--parallel N` orchestration с явным work-item routing;
  - запускать воркеры в isolated worktrees с deterministic branch/worktree naming;
  - собирать stage results без конфликта artifact roots и без shared-write ambiguity.
  **AC:** parallel loop-run может запускать независимые work items в изоляции и корректно собирать per-worker outcomes.
  **Deps:** W123-2
  **Regression/tests:** `python3 -m pytest -q tests/test_parallel_loop_run.py`, `tests/repo_tools/parallel-loop-regression.sh`.
  **Effort:** L
  **Risk:** High

- [ ] **W123-4 (P2) Consolidation, reporting, docs, and regression suite** `skills/aidd-flow-state/runtime/tasklist_consolidate.py`, `skills/aidd-flow-state/runtime/tasklist_normalize.py`, `skills/aidd-observability/runtime/aggregate_report.py`, `templates/aidd/docs/loops/README.md`, `templates/aidd/AGENTS.md`, `tests/test_scheduler.py`, `tests/test_parallel_loop_run.py`, `tests/repo_tools/parallel-loop-regression.sh`:
  - консолидировать per-work-item outcomes обратно в tasklist, progress log и next actions;
  - агрегировать ticket-level report по узлам, tests и stage results;
  - оформить operator docs и regression suite для parallel workflow.
  **AC:** parallel results детерминированно возвращаются в основной tasklist без дублей; docs и regression suite покрывают scheduler, worker crash, stale locks и path conflicts.
  **Deps:** W123-3
  **Regression/tests:** `python3 -m pytest -q tests/test_scheduler.py tests/test_parallel_loop_run.py`, `tests/repo_tools/parallel-loop-regression.sh`.
  **Effort:** M
  **Risk:** Medium

## Wave 124 — OpenCode Host Adaptation (2026-04-02)

_Статус: plan. Основание — low-priority platform adaptation для OpenCode с целью near-full parity без форка runtime и без раздвоения stage logic. Shared Python runtime, stage templates и `aidd/**` остаются общими; Claude и OpenCode получают отдельные generated host layers._

- [ ] **W124-1 (P2) Host-neutral runtime and environment contract** `aidd_runtime/__init__.py`, `tests/repo_tools/cli-adapter-guard.py`, `docs/skill-language.md`, `AGENTS.md`, `tests/test_prompt_lint.py`:
  - ввести host-neutral canonical alias для plugin/runtime root, чтобы runtime help, docs examples и guards не зависели только от `CLAUDE_PLUGIN_ROOT`;
  - сохранить `CLAUDE_PLUGIN_ROOT` как compatibility alias для Claude host;
  - отделить canonical Python runtime contract от host-specific launcher examples и invocation semantics.
  **AC:** runtime entrypoints, help-output и doc examples поддерживают host-neutral env contract; Claude compatibility остаётся рабочей без special-case regressions.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_prompt_lint.py`, `python3 tests/repo_tools/cli-adapter-guard.py`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W124-2 (P2) Generated OpenCode commands and agents from shared source** `agents/*.md`, `skills/*/SKILL.md`, `.claude-plugin/plugin.json`, `.opencode/commands/*.md`, `.opencode/agents/*.md`, `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py`:
  - определить canonical metadata source для генерации host surfaces из существующих stage commands и agent prompts;
  - генерировать OpenCode command и agent surfaces без ручного дублирования prompt content;
  - зафиксировать mapping между Claude slash commands и OpenCode command surface на одном canonical source.
  **AC:** все публичные стадии и ключевые stage agents имеют generated OpenCode host surfaces; изменения в shared prompt source воспроизводимо отражаются и в Claude, и в OpenCode layers.
  **Deps:** W124-1
  **Regression/tests:** `python3 -m pytest -q tests/test_prompt_lint.py`, `python3 tests/repo_tools/lint-prompts.py --root .`.
  **Effort:** L
  **Risk:** High

- [ ] **W124-3 (P2) OpenCode launcher, loop, and non-interactive runner parity** `skills/aidd-loop/runtime/loop_run.py`, `skills/aidd-loop/runtime/loop_step.py`, `tests/repo_tools/aidd_stage_launcher.py`, `tests/repo_tools/aidd_audit_runner.py`, `tests/test_loop_run.py`, `tests/test_loop_step.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - ввести host adapter для runner selection вместо жёсткой привязки к `claude -p`;
  - адаптировать seed-stage и auto-loop non-interactive execution под OpenCode runner path;
  - формализовать OpenCode-safe init evidence и diagnostics так, чтобы audit tooling различал host mode без branch explosion.
  **AC:** seed stages и loop runner могут запускаться через OpenCode non-interactive surface; runtime и audit не считают `claude -p` единственным допустимым launcher.
  **Deps:** W124-1, W124-2
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_run.py tests/test_loop_step.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** L
  **Risk:** High

- [ ] **W124-4 (P2) Host-aware lint, smoke, and audit tooling** `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/smoke-workflow.sh`, `tests/repo_tools/aidd_stage_launcher.py`, `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/test_aidd_stage_launcher.py`, `tests/repo_tools/test_aidd_audit_runner.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - разделить canonical runtime checks и host-specific checks для Claude и OpenCode;
  - добавить host selector в smoke/audit fixtures и repo tools, где сейчас зашит Claude-only init/launcher contract;
  - исключить ложные FAIL/WARN из-за host mismatch при сохранении текущего Claude CI baseline.
  **AC:** tooling валидирует Claude и OpenCode независимо; canonical runtime checks больше не содержат Claude-only assumptions, а host-specific audit checks остаются детерминированными.
  **Deps:** W124-1, W124-2, W124-3
  **Regression/tests:** `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/smoke-workflow.sh`, `python3 -m pytest -q tests/repo_tools/test_aidd_stage_launcher.py tests/repo_tools/test_aidd_audit_runner.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W124-5 (P2) Host-aware docs and installation/distribution surfaces** `README.md`, `README.en.md`, `AGENTS.md`, `.claude-plugin/plugin.json`, `opencode.json`, `.opencode/plugins/*`, `CHANGELOG.md`:
  - отделить Claude-specific install/use path от canonical AIDD runtime model;
  - добавить OpenCode installation, usage и host-compatibility guidance;
  - явно зафиксировать supported hosts, compatibility layer и границы parity в user/dev docs и release surfaces.
  **AC:** документация и package surfaces больше не описывают AIDD как Claude-only plugin; documented install/use path присутствует и для Claude, и для OpenCode.
  **Deps:** W124-1, W124-2
  **Regression/tests:** `tests/repo_tools/ci-lint.sh`, `python3 tests/repo_tools/lint-prompts.py --root .`.
  **Effort:** S
  **Risk:** Medium
