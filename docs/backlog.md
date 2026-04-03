# Product Backlog

> INTERNAL/DEV-ONLY: engineering wave planning and execution tracker.

_Revision note (2026-04-02): backlog нормализован в пять активных wave. Дубликаты, historical incident notes и superseded blocks удалены; backlog отражает только исполнимые программы работ, а крупные platform adaptations вынесены в отдельные low-priority wave._


## Wave 127 — E2E quality follow-ups for TST-002 (2026-04-03)

Статус: plan. Основание — результаты quality e2e run 20260403T072014Z по тикету TST-002; цель — повысить качество кода и артефактов, генерируемых AIDD.

### Source run
- Audit dir: `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260403T072014Z`
- Base prompt: `/Users/griogrii_riabov/grigorii_projects/ai_driven_dev/docs/e2e/aidd_test_flow_prompt_ralph_script_full.txt`
- Feature final state: `NOT_REACHED`
- Overall quality gate: `FAIL`

- [ ] **W127-1 (P0) plan-new convergence and terminal result contract** `skills/plan-new/SKILL.md`, `agents/planner.md`, `skills/plan-new/runtime/research_check.py`, `tests/test_planner_agent.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - ввести bounded convergence guard для `plan-new` и запрет бесконечных nested loops без top-level result;
  - эмитить deterministic terminal payload с `reason_code` вместо зависания до внешнего terminate;
  - добавить e2e contract-проверку `result_count>0` для успешных и recoverable выходов.
  **AC:** `plan-new` в e2e run формирует top-level result в пределах budget; `result_count=0` не остаётся без explicit terminal classification.
  **Deps:** W126-1
  **Regression/tests:** `python3 -m pytest -q tests/test_planner_agent.py tests/repo_tools/test_e2e_prompt_contract.py`
  **Evidence:** `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260403T072014Z/05_plan_new_run1.summary.txt`, `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260403T072014Z/05_plan_new_run2.summary.txt`
  **Effort:** M
  **Risk:** High

- [ ] **W127-2 (P1) Prompt contraction for idea/plan latency and determinism** `skills/idea-new/SKILL.md`, `skills/plan-new/SKILL.md`, `agents/analyst.md`, `agents/planner.md`, `tests/test_prompt_lint.py`:
  - сократить prompt-ветки, которые провоцируют глубокие многократные subagent cycles до первого operator-visible результата;
  - зафиксировать deterministic question-closure path (`compact_q_values`) без лишних reread/retry циклов;
  - добавить lint-правило против long-form non-convergent orchestration hints в stage skills.
  **AC:** `idea-new`/`plan-new` завершают первичный stage-return без каскадных внутренних reread-loop по тем же input artifacts.
  **Deps:** W127-1
  **Regression/tests:** `python3 -m pytest -q tests/test_prompt_lint.py tests/repo_tools/test_e2e_prompt_contract.py`
  **Evidence:** `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260403T072014Z/05_idea_new_run1.log`, `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260403T072014Z/05_plan_new_run2.log`
  **Effort:** M
  **Risk:** Medium

- [ ] **W127-3 (P2) Runner lock and parallel-call cancellation hardening** `skills/aidd-core/SKILL.md`, `skills/plan-new/SKILL.md`, `hooks/hooks.json`, `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/test_aidd_audit_runner.py`:
  - ужесточить stage-run mutual exclusion и guard против concurrent tool invocations для одного ticket/stage;
  - добавить явную диагностику race/cancel (`parallel_call_cancelled`) с рекомендацией единственного recovery-path;
  - покрыть race-сценарий регрессионным audit-runner тестом.
  **AC:** плановый stage-run не генерирует повторяющиеся `Cancelled: parallel tool call ... errored` при корректном single-run запуске.
  **Deps:** W127-1
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_aidd_audit_runner.py tests/repo_tools/test_e2e_prompt_contract.py`
  **Evidence:** `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260403T072014Z/05_plan_new_run1.log`
  **Effort:** S
  **Risk:** Medium

- [ ] **W127-4 (P2) RLM link-evidence completeness for reviewed research** `skills/researcher/SKILL.md`, `skills/researcher/runtime/research.py`, `skills/aidd-rlm/runtime/rlm_slice.py`, `tests/test_research_check.py`, `tests/test_research_rlm_e2e.py`:
  - добавить post-check для `reviewed` статуса: пустой `rlm.links` допускается только с explicit constrained-scope explanation;
  - усилить guidance для `--paths/--keywords`, чтобы links не оставались empty при релевантном code scope;
  - расширить e2e тесты на `rlm_links_empty_warn` с проверкой quality narrative.
  **AC:** при `research_status=reviewed` links либо непустые, либо присутствует корректный explicit quality disclaimer и remediation hints.
  **Deps:** W127-2
  **Regression/tests:** `python3 -m pytest -q tests/test_research_check.py tests/test_research_rlm_e2e.py`
  **Evidence:** `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260403T072014Z/05_researcher_run1.summary.txt`, `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260403T072014Z/05_research_artifact_presence.txt`
  **Effort:** S
  **Risk:** Medium

## Wave 126 — E2E quality follow-ups for TST-002 (2026-04-03)

Статус: plan. Основание — результаты quality e2e run 20260403T044337Z по тикету TST-002; цель — повысить качество кода и артефактов, генерируемых AIDD.

### Source run
- Audit dir: `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260403T044337Z`
- Base prompt: `/Users/griogrii_riabov/grigorii_projects/ai_driven_dev/docs/e2e/aidd_test_flow_prompt_ralph_script_full.txt`
- Feature final state: `NOT_REACHED`
- Overall quality gate: `FAIL`

- [ ] **W126-1 (P0) Seed stage-chain artifact contract hardening** `skills/implement/runtime/implement_run.py`, `skills/review/runtime/review_run.py`, `skills/aidd-loop/runtime/loop_run.py`, `skills/aidd-loop/runtime/loop_step_stage_chain.py`, `tests/test_loop_run.py`:
  - обеспечить обязательный non-empty stage-chain artifact bundle перед loop handoff;
  - синхронизовать seed-stage success criteria с preloop integrity checks (no empty stage-chain trees);
  - добавить deterministic failure payload с actionable recovery вместо downstream skip cascade.
  **AC:** `06_preloop_integrity_check.txt` больше не даёт `preloop_artifacts_missing` при успешных implement/review runs.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_run.py tests/test_loop_step.py tests/test_review_run.py`.
  **Evidence:** `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260403T044337Z/06_preloop_integrity_check.txt`
  **Effort:** M
  **Risk:** High

- [ ] **W126-2 (P1) tasks-new canonical orchestration and TEST_EXECUTION parser alignment** `skills/tasks-new/runtime/tasks_new.py`, `skills/tasks-new/SKILL.md`, `skills/aidd-flow-state/runtime/tasklist_check.py`, `tests/test_tasks_new.py`, `tests/test_tasklist_check.py`:
  - удалить manual-spec/manual-tasklist recovery path из primary orchestration narrative;
  - ужесточить parser/validator для `AIDD:TEST_EXECUTION` без false missing-tasks сигналов;
  - вернуть единый canonical recovery hint через allowed stage commands.
  **AC:** `05_tasks_new_drift_check.txt` = OK и `05_tasklist_test_execution_probe.txt` без schema-mismatch WARN для валидного tasklist.
  **Deps:** W126-1
  **Regression/tests:** `python3 -m pytest -q tests/test_tasks_new.py tests/test_tasklist_check.py`.
  **Evidence:** `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260403T044337Z/05_tasks_new_drift_check.txt`, `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260403T044337Z/05_tasklist_test_execution_probe.txt`
  **Effort:** S
  **Risk:** Medium

- [ ] **W126-3 (P1) Implement runtime handoff entrypoint contract fix** `skills/implement/runtime/implement_run.py`, `skills/aidd-flow-state/runtime/progress_cli.py`, `skills/aidd-flow-state/runtime/status_summary.py`, `tests/test_implement_agent.py`:
  - убрать/заменить вызов отсутствующего `handoff_check.py` на существующий canonical runtime surface;
  - добавить fail-fast validation entrypoint paths до запуска nested runtime commands;
  - эмитить explicit contract_mismatch marker вместо silent tool-result noise.
  **AC:** implement logs больше не содержат `can't open file ... handoff_check.py` для canonical runs.
  **Deps:** W126-1
  **Regression/tests:** `python3 -m pytest -q tests/test_implement_agent.py tests/test_prompt_contract_runtime_paths.py`.
  **Evidence:** `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260403T044337Z/06_implement_runtime_path_drift_hits.txt`
  **Effort:** S
  **Risk:** Medium

- [ ] **W126-4 (P1) Workspace reconciliation guard for subagent worktrees** `skills/implement/runtime/implement_run.py`, `skills/review/runtime/review_run.py`, `skills/aidd-loop/runtime/loop_run_parts/core.py`, `tests/test_implement_agent.py`, `tests/test_review_run.py`:
  - ввести post-stage reconciliation check: declared implementation must appear in tracked workspace diff;
  - блокировать stage success при расхождении между artifact claims и landed code delta;
  - добавить telemetry marker `workspace_reconcile_failed` для quality/e2e diagnostics.
  **AC:** stage success невозможен при “artifact-heavy / code-light” расхождении; mismatch детерминированно отражается в report.
  **Deps:** W126-1
  **Regression/tests:** `python3 -m pytest -q tests/test_implement_agent.py tests/test_review_run.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Evidence:** `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260403T044337Z/09_quality_sources.txt`
  **Effort:** M
  **Risk:** High

- [ ] **W126-5 (P1) Research narrative quality gate against placeholder-heavy output** `skills/researcher/runtime/research.py`, `skills/researcher/templates/research.template.md`, `skills/aidd-core/runtime/research_guard.py`, `tests/test_research_command.py`, `tests/test_research_check.py`:
  - добавить quality checks на placeholder density (`TBD`, empty sections) в research summary;
  - ограничить readiness propagation при warn-status без concrete integration evidence;
  - включить actionable remediation hints с конкретными paths/queries.
  **AC:** research summary для READY downstream не содержит placeholder-heavy sections и содержит concrete integration points.
  **Deps:** W126-2
  **Regression/tests:** `python3 -m pytest -q tests/test_research_command.py tests/test_research_check.py tests/test_gate_workflow.py`.
  **Evidence:** `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260403T044337Z/05_research_rlm_check.txt`, `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260403T044337Z/09_artifact_findings.md`
  **Effort:** S
  **Risk:** Medium

## Wave 125 — E2E quality follow-ups for TST-002 (2026-04-02)

Статус: plan. Основание — результаты quality e2e run 20260402T191116Z по тикету TST-002; цель — повысить качество кода и артефактов, генерируемых AIDD.

### Source run
- Audit dir: `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260402T191116Z`
- Base prompt: `/Users/griogrii_riabov/grigorii_projects/ai_driven_dev/docs/e2e/aidd_test_flow_prompt_ralph_script_full.txt`
- Feature final state: `NOT_REACHED`
- Overall quality gate: `FAIL`

- [ ] **W125-1 (P1) review-spec narrative/report parity hardening** `skills/aidd-core/runtime/prd_review.py`, `skills/aidd-core/runtime/prd_review_section.py`, `skills/review-spec/SKILL.md`, `tests/test_prd_review_agent.py`:
  - вычислять user-facing narrative только из structured report payload и запретить расхождение по findings/recommended_status;
  - добавить fail-fast telemetry для `narrative_vs_report_mismatch` с deterministic recovery hint;
  - синхронизовать stage-output и report pack generation в одном source-of-truth.
  **AC:** `narrative_vs_report_mismatch=0` в e2e run; downstream recovery decisions строятся только по structured report.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_prd_review_agent.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Evidence:** `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260402T191116Z/05_review_spec_report_check_run1.txt`
  **Effort:** S
  **Risk:** Medium

- [ ] **W125-2 (P1) Research readiness hardening against placeholder evidence** `skills/researcher/runtime/research.py`, `skills/aidd-core/runtime/research_guard.py`, `templates/aidd/config/gates.json`, `tests/test_research_command.py`, `tests/test_research_check.py`:
  - добавить quality validators для research markdown (placeholder/TBD density, required sections with concrete links);
  - запретить soft-pass readiness без минимально полезного narrative evidence при `research_status=warn|pending`;
  - расширить diagnostics для operator decision (`what is missing`, `where to fill`, `next command`).
  **AC:** readiness gate не проходит при placeholder-heavy research без explicit override; quality diagnostics детерминированы.
  **Deps:** W125-1
  **Regression/tests:** `python3 -m pytest -q tests/test_research_command.py tests/test_research_check.py tests/test_gate_workflow.py`.
  **Evidence:** `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260402T191116Z/09_research_placeholder_check.txt`, `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260402T191116Z/05_precondition_block.txt`
  **Effort:** M
  **Risk:** High

- [ ] **W125-3 (P2) QA report fidelity for executed tests** `skills/qa/runtime/qa.py`, `skills/qa/runtime/qa_parts/core.py`, `tests/test_qa_agent.py`, `tests/test_qa_exit_code.py`:
  - прокинуть агрегированные executed-tests поля из canonical tests log в `aidd/reports/qa/<ticket>.json`;
  - синхронизовать `tests_summary`, `tests_executed`, и review/test markers;
  - добавить regression на parity между QA report и tests log.
  **AC:** QA report содержит непротиворечивые executed tests details (count/runner/failures/errors) при PASS/WARN/FAIL.
  **Deps:** W125-2
  **Regression/tests:** `python3 -m pytest -q tests/test_qa_agent.py tests/test_qa_exit_code.py`.
  **Evidence:** `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260402T191116Z/08_qa_gradle_check.txt`, `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/aidd/reports/qa/TST-002.json`
  **Effort:** S
  **Risk:** Medium

- [ ] **W125-4 (P2) Tasklist/report reference integrity checks** `skills/tasks-new/runtime/tasks_new.py`, `skills/aidd-flow-state/runtime/tasklist_check.py`, `skills/plan-new/SKILL.md`, `tests/test_tasks_new.py`, `tests/test_tasklist_check.py`:
  - валидировать существование report/test paths перед установкой `Status: READY` в tasklist;
  - исключить stale placeholders в plan/tasklist headers (path drift guard);
  - возвращать actionable warning с canonical regeneration command.
  **AC:** tasklist/plan не публикуют несуществующие report paths; integrity check покрыт тестами.
  **Deps:** W125-2
  **Regression/tests:** `python3 -m pytest -q tests/test_tasks_new.py tests/test_tasklist_check.py`.
  **Evidence:** `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260402T191116Z/09_tasklist_reference_check.txt`, `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/aidd/docs/tasklist/TST-002.md`
  **Effort:** S
  **Risk:** Medium

- [ ] **W125-5 (P2) Loop convergence policy for no-tests soft blocks** `skills/aidd-loop/runtime/loop_run_parts/core.py`, `skills/aidd-loop/runtime/loop_step_parts/core.py`, `skills/aidd-loop/runtime/loop_block_policy.py`, `tests/test_loop_run.py`, `tests/test_loop_step.py`:
  - добавить deterministic branch для `no_tests_soft` с bounded transition к next actionable stage вместо max-iteration churn;
  - улучшить termination reason mapping (`max-iterations` vs actionable blocked) и operator hints;
  - расширить policy-matrix tests для `ralph` soft-class behavior.
  **AC:** loop не зацикливается на soft-block review без прогресса; terminal output содержит actionable next step.
  **Deps:** W125-2
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_run.py tests/test_loop_step.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Evidence:** `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260402T191116Z/07_loop_run1.log`, `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260402T191116Z/07_recoverable_block_policy_check.txt`
  **Effort:** M
  **Risk:** Medium

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
