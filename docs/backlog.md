# Product Backlog

> INTERNAL/DEV-ONLY: engineering wave planning and execution tracker.

Owner: feature-dev-aidd
Last reviewed: 2026-04-12
Status: active

_Revision note (2026-04-09): стабилизационный трек `120 -> 121 -> 136` закрыт (runtime/core -> prompt/audit -> integration closure). Волны `122..125` остаются roadmap-приоритетом._

## Archived Completed Waves

- Historical completed waves `120`, `121`, `136` moved to `docs/backlog-archive-w120-w121-w136.md`.
- Local evidence note: references like `aidd/reports/**` point to workspace-local artifacts and are not part of this git repository.

## Wave 139 — Cleanup Signal Quality (2026-04-13)

_Статус: plan. Основание — conservative cleanup показал ложноположительные `safe-to-delete` сигналы в repo topology audit для e2e prompt artifacts с indirect usage через генераторы и contract tests._

- [ ] **W139-1 (P1) Reduce false-positive `safe-to-delete` in topology audit** `tests/repo_tools/repo_topology_audit.py`, `tests/test_repo_topology_audit.py`, `tests/repo_tools/build_e2e_prompts.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - учесть indirect usage через glob/path-composition из генераторов и contract tests, чтобы `safe` triage не предлагал удалять реально используемые артефакты;
  - добавить protected-path heuristic для generated e2e prompt outputs;
  - добавить regression case для `docs/e2e/aidd_test_flow_prompt_ralph_script.txt`.
  **AC:** audit больше не маркирует используемые e2e prompt artifacts как `safe-to-delete`; regression test фиксирует кейс.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_repo_topology_audit.py tests/repo_tools/test_e2e_prompt_contract.py`, `python3 tests/repo_tools/repo_topology_audit.py --repo-root . --output-json /tmp/repo-revision.graph.json --output-md /tmp/repo-revision.md --output-cleanup /tmp/repo-cleanup-plan.json`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W139-2 (P2) Cleanup governance sync for generated report policy** `docs/revision/repo-revision.md`, `tests/repo_tools/repo_topology_audit.py`, `tests/test_repo_topology_audit.py`:
  - согласовать auto-triage `safe-to-delete` c текущей governance policy cleanup wave;
  - зафиксировать regression case, что active governance docs не попадают в `safe-to-delete` без явного archival decision.
  **AC:** generated revision report не конфликтует с принятой cleanup policy по active governance docs.
  **Deps:** W139-1
  **Regression/tests:** `python3 -m pytest -q tests/test_repo_topology_audit.py`, `python3 tests/repo_tools/repo_topology_audit.py --repo-root . --output-json /tmp/repo-revision.graph.json --output-md /tmp/repo-revision.md --output-cleanup /tmp/repo-cleanup-plan.json`.
  **Effort:** S
  **Risk:** Low

## Wave 137 — Implement Stage Non-Convergence Hardening (2026-04-11)

_Статус: plan. Основание — TST-001 full audit показал implement-stage non-convergence (`task_started` без `task_completed`), отсутствие top-level terminal result и неоднозначную классификацию завершения `exit_code=143` при stall/retry paths._

- [ ] **W137-1 (P0) Bounded implement completion + canonical terminal fallback** `skills/implement/runtime/implement_run.py`, `skills/aidd-core/runtime/stage_actions_run.py`, `skills/aidd-flow-state/runtime/stage_result.py`, `tests/test_implementer_prompt.py`, `tests/test_loop_step.py`, `tests/test_stage_result.py`:
  - ввести bounded guard для implement subagent-run, чтобы stage не зависал без terminal outcome;
  - при non-convergence/timeout эмитить deterministic canonical `aidd.stage_result.v1` (blocked), а не оставлять run без top-level result;
  - сохранить current stage-result contract без legacy fallback path.
  **AC:** implement stage всегда завершает run terminal payload-ом (`done|blocked`) с canonical schema; сценарий `task_started` без завершения больше не оставляет hanging outcome.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_implementer_prompt.py tests/test_loop_step.py tests/test_stage_result.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W137-2 (P0) Loop-step terminal invariant for missing top-level result** `skills/aidd-loop/runtime/loop_step_parts/core.py`, `skills/aidd-loop/runtime/loop_step_stage_chain.py`, `skills/aidd-loop/runtime/loop_step_stage_result.py`, `tests/test_loop_step.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - закрепить invariant: после stage-run должен быть terminal signal + canonical stage result;
  - если terminal signal отсутствует, детерминированно переводить outcome в blocked с reason surface вместо silent non-result path;
  - синхронизовать diagnostics, чтобы `no_top_level_result` не терял причинно-следственную связь.
  **AC:** loop-step не завершает stage с пустым/неопределённым top-level outcome; missing-result path детерминированно классифицируется и репортится.
  **Deps:** W137-1
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_step.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W137-3 (P0) Exit-143 attribution normalization and watchdog precedence** `skills/aidd-loop/runtime/loop_run_parts/core.py`, `tests/test_loop_run.py`, `tests/repo_tools/test_aidd_audit_runner.py`, `tests/repo_tools/test_aidd_stage_launcher.py`:
  - унифицировать ветку классификации `exit_code=143` по watchdog-marker/killed semantics;
  - исключить ambiguous mapping, когда termination интерпретируется не тем классом причины;
  - выровнять runtime vs audit tooling reason precedence.
  **AC:** `exit_code=143` классифицируется однозначно и повторяемо (watchdog vs external terminate) в runtime и audit runner.
  **Deps:** W137-2
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_run.py tests/repo_tools/test_aidd_audit_runner.py tests/repo_tools/test_aidd_stage_launcher.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W137-4 (P1) Stream-path missing telemetry hardening for liveness/stall** `tests/repo_tools/aidd_stage_launcher.py`, `tests/repo_tools/aidd_stream_paths.py`, `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/test_aidd_stage_launcher.py`, `tests/repo_tools/test_aidd_audit_runner.py`:
  - при `stream_path_not_emitted_by_cli` не повышать сигнал до terminal сам по себе;
  - подтверждать stall только при отсутствии роста и main log, и валидных stream/event источников;
  - расширить diagnostics, чтобы parser-noise не маскировал primary причину stage-failure.
  **AC:** отсутствие stream-path не даёт ложного terminal вывода; stall-классификация устойчиво отделяет telemetry gap от реальной стагнации.
  **Deps:** W137-3
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_aidd_stage_launcher.py tests/repo_tools/test_aidd_audit_runner.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W137-5 (P1) Implementer prompt containment + replay fixture for non-convergence** `skills/implement/SKILL.md`, `agents/implementer.md`, `tests/fixtures/audit_tst001/*`, `tests/repo_tools/test_e2e_prompt_contract.py`, `docs/runbooks/tst001-audit-hardening.md`:
  - сузить implement handoff envelope: один work-item/итерация, bounded retries, обязательный terminal return contract;
  - добавить replay fixture для кейса `task_started` без terminal completion;
  - зафиксировать runbook guidance для deterministic recovery path без manual/non-canonical обходов.
  **AC:** prompt/replay suite воспроизводит и предотвращает implement non-convergence drift; оператор получает один canonical recovery path.
  **Deps:** W137-1, W137-2
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py tests/test_implementer_prompt.py`.
  **Effort:** S
  **Risk:** Medium

## Wave 138 — E2E Flow Consistency & QA Policy Stabilization (2026-04-11)

_Статус: plan. Основание — full audit TST-001: terminal `qa_blocked_no_tests_hard`, `review_spec_report_mismatch`, loop warnings (`non_loop_stage_recovered`, `output_contract_warn`) и recoverable `contract_mismatch_actions_shape` в QA._

- [ ] **W138-1 (P0) QA missing-test-infra policy: deterministic WARN path instead of terminal block** `skills/qa/runtime/qa.py`, `skills/qa/runtime/qa_parts/core.py`, `templates/aidd/config/gates.json`, `skills/tasks-new/runtime/tasks_new.py`, `tests/test_qa_agent.py`, `tests/test_qa_exit_code.py`, `tests/test_tasklist_check.py`:
  - добавить preflight исполнимости test-commands до QA execution;
  - при отсутствии test infra применять policy-driven soft outcome (WARN) с явным reason_code и diagnostics;
  - сохранять hard-block только для случаев, где test infra существует, но тесты реально fail.
  **AC:** отсутствие test infra больше не приводит к terminal `NOT VERIFIED`; QA outcome детерминирован и policy-driven.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_qa_agent.py tests/test_qa_exit_code.py tests/test_tasklist_check.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W138-2 (P0) `review-spec` payload-first narrative synchronization** `skills/aidd-core/runtime/prd_review.py`, `skills/review-spec/SKILL.md`, `tests/test_prd_review_agent.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - закрепить structured payload (`recommended_status/findings`) как единственный source-of-truth для stage narrative;
  - исключить кейс, когда narrative сообщает critical/high findings при пустом structured findings;
  - синхронизовать финальный текст stage-output с report payload.
  **AC:** `narrative_vs_structured_mismatch` не воспроизводится в штатном пути.
  **Deps:** W138-1
  **Regression/tests:** `python3 -m pytest -q tests/test_prd_review_agent.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W138-3 (P0) Loop pre-run state normalization and stale-stage guardrails** `skills/aidd-loop/runtime/loop_run.py`, `skills/aidd-loop/runtime/loop_step_parts/core.py`, `skills/aidd-loop/runtime/loop_run_parts/core.py`, `tests/test_loop_run.py`, `tests/test_loop_step.py`:
  - перед первым loop step нормализовать active stage/work item из canonical источников;
  - убрать warning-classification для успешно self-healed stale stage (оставить telemetry marker);
  - предотвратить старт loop с non-loop active stage как baseline state.
  **AC:** `non_loop_stage_recovered` не возникает как flow warning в нормальном пути.
  **Deps:** W138-1
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_run.py tests/test_loop_step.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W138-4 (P1) Output contract completeness for implement/review loop artifacts** `skills/implement/runtime/implement_run.py`, `skills/review/runtime/review_run.py`, `skills/aidd-loop/runtime/loop_step_stage_result.py`, `tests/test_loop_run.py`, `tests/test_review_run.py`:
  - enforce обязательные output fields (`status`, `read_log`, `tests`, `next_actions`, `work_item_key`, `artifacts`);
  - устранить `output_contract_warn` при корректном stage completion;
  - синхронизовать output-contract validator и stage producers.
  **AC:** `output.contract.status=warn` из-за missing required fields не воспроизводится.
  **Deps:** W138-3
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_run.py tests/test_review_run.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W138-5 (P1) QA actions contract hardening (prevent recovered shape errors)** `skills/qa/runtime/qa_run.py`, `skills/aidd-docio/runtime/actions_validate.py`, `skills/aidd-docio/runtime/actions_apply.py`, `tests/test_stage_actions_run.py`, `tests/test_qa_agent.py`:
  - валидировать/canonicalize `aidd.actions.v1` до apply без повторных fail-циклов;
  - запретить невалидные `kind` и пустые/non-canonical action forms;
  - оставить один deterministic fail path при irrecoverable actions mismatch.
  **AC:** `contract_mismatch_actions_shape` не возникает в штатном QA пути.
  **Deps:** W138-1
  **Regression/tests:** `python3 -m pytest -q tests/test_stage_actions_run.py tests/test_qa_agent.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W138-6 (P1) Replay fixtures + audit contract updates for TST-001 findings** `tests/fixtures/audit_tst001/*`, `tests/repo_tools/test_aidd_audit_runner.py`, `tests/repo_tools/test_e2e_prompt_contract.py`, `tests/repo_tools/e2e_prompt/profile_full.md`, `docs/runbooks/tst001-audit-hardening.md`:
  - добавить replay-кейсы для `qa no_tests_soft/warn`, `review-spec mismatch`, `loop stale state`, `actions shape mismatch`;
  - обновить e2e prompt contract ожидания под новую policy и классификацию;
  - зафиксировать reason precedence для terminal/non-terminal сигналов.
  **AC:** найденные в TST-001 инциденты воспроизводятся и проверяются в CI детерминированно.
  **Deps:** W138-1, W138-2, W138-3, W138-5
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_aidd_audit_runner.py tests/repo_tools/test_e2e_prompt_contract.py`.
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
