# Product Backlog Archive — Waves 120/121/136

> INTERNAL/DEV-ONLY: archived completed waves moved from `docs/backlog.md`.

Owner: feature-dev-aidd
Last reviewed: 2026-04-12
Status: historical

_Local evidence note: references like `aidd/reports/**` point to workspace-local artifacts and are not part of this git repository._

## Wave 120 — Core Runtime & Stage Contracts Stabilization (2026-04-06)

_Статус: done (2026-04-09). Основание — закрытие terminal flow инцидентов из TST-class аудитов: seed non-convergence, stage-result contract drift, scope/work-item drift, timeout attribution, research gate ambiguity, QA/tasklist execution mismatch и workspace layout violations._
_Evidence: `docs/runbooks/w120-w121-w136-closure.md`, `aidd/reports/events/w120-w121-w136-baseline-2026-04-09.md`._

- [x] **W120-1 (P0) Seed-stage convergence and bounded fail-fast for repeated command failures** `skills/aidd-loop/runtime/loop_run_parts/core.py`, `skills/implement/runtime/implement_run.py`, `skills/review/runtime/review_run.py`, `skills/qa/runtime/qa_parts/core.py`, `tests/test_loop_run.py`, `tests/test_implementer_prompt.py`, `tests/test_review_run.py`, `tests/test_qa_agent.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - ввести convergence guard для seed-runs с deterministic terminal payload;
  - добавить fail-fast reason `repeated_command_failure_no_new_evidence` для повторяющихся одинаковых command failures без нового evidence;
  - исключить `result_count=0` без top-level terminal payload при валидном init.
  **AC:** seed stages не зависают в рекурсивных ретраях одинаковой ошибки; terminal payload deterministic.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_run.py tests/test_review_run.py tests/test_qa_agent.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** High

- [x] **W120-2 (P0) Canonical preflight/actions/stage_result contract only** `skills/aidd-core/runtime/stage_actions_run.py`, `skills/aidd-flow-state/runtime/stage_result.py`, `skills/aidd-docio/runtime/actions_validate.py`, `skills/aidd-docio/runtime/actions_apply.py`, `tests/test_stage_actions_run.py`, `tests/test_gate_workflow_preflight_contract.py`, `tests/test_wave93_validators.py`, `tests/test_prompt_lint.py`:
  - закрепить canonical-only `aidd.stage_result.v1` shape на preflight/terminal boundaries;
  - блокировать manual stage-result write/copy recovery path как primary route;
  - завершать invalid actions payload одним deterministic blocked result.
  **AC:** preflight и stage_result artifacts всегда canonical; manual recovery path не является штатным.
  **Deps:** W120-1
  **Regression/tests:** `python3 -m pytest -q tests/test_stage_actions_run.py tests/test_gate_workflow_preflight_contract.py tests/test_wave93_validators.py tests/test_prompt_lint.py`.
  **Effort:** M
  **Risk:** High

- [x] **W120-3 (P0) Canonical scope/work_item authority and fallback guardrails** `skills/aidd-loop/runtime/loop_step_stage_result.py`, `skills/aidd-loop/runtime/loop_step_parts/core.py`, `skills/aidd-loop/runtime/loop_run_parts/core.py`, `skills/aidd-flow-state/runtime/stage_result.py`, `tests/test_loop_step.py`, `tests/test_loop_run.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - один authoritative resolver для `scope_key/work_item_key`;
  - fallback между scope только при recoverable diagnostics, иначе deterministic block;
  - исключить cross-scope stale fallback как скрытый success path.
  **AC:** одна итерация работает в одном canonical scope namespace; scope drift даёт прозрачную классификацию.
  **Deps:** W120-2
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_step.py tests/test_loop_run.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** High

- [x] **W120-4 (P0) Timeout/143 attribution and loop retry policy hardening** `skills/aidd-loop/runtime/loop_block_policy.py`, `skills/aidd-loop/runtime/loop_run_parts/core.py`, `skills/aidd-loop/runtime/loop_step_parts/core.py`, `tests/test_loop_run.py`, `tests/test_loop_step.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - детерминировать классификацию `watchdog_terminated` vs `parent_terminated_or_external_terminate`;
  - синхронизовать stage-budget/step-timeout semantics между runtime и prompt contracts;
  - оставить bounded recoverable retries для `ralph`, strict-policy без деградации.
  **AC:** `exit_code=143` и timeout paths классифицируются однозначно и повторяемо.
  **Deps:** W120-3
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_run.py tests/test_loop_step.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** High

- [x] **W120-5 (P0) Research gate convergence + soft-readiness quality floor** `skills/researcher/runtime/research.py`, `skills/aidd-rlm/runtime/rlm_links_build.py`, `skills/aidd-rlm/runtime/rlm_finalize.py`, `skills/aidd-core/runtime/research_guard.py`, `skills/plan-new/runtime/research_check.py`, `templates/aidd/config/gates.json`, `tests/test_research_command.py`, `tests/test_research_check.py`, `tests/test_gate_workflow.py`, `tests/test_research_rlm_e2e.py`:
  - снизить ложные `pending/links_empty` через bounded finalize path;
  - усилить diagnostics для `warn/pending/invalid/missing` с явным remediation payload;
  - сохранить soft-readiness только при минимальном baseline и явных quality markers.
  **AC:** research gate отделяет recoverable/hard-blocking причины и даёт детерминированный convergence path.
  **Deps:** W120-1
  **Regression/tests:** `python3 -m pytest -q tests/test_research_command.py tests/test_research_check.py tests/test_gate_workflow.py tests/test_research_rlm_e2e.py tests/test_loop_run.py`.
  **Effort:** L
  **Risk:** High

- [x] **W120-6 (P0) QA/tasklist execution contract and cwd-aware command handling** `skills/tasks-new/runtime/tasks_new.py`, `skills/tasks-new/templates/tasklist.template.md`, `skills/qa/runtime/qa.py`, `skills/qa/runtime/qa_parts/core.py`, `skills/qa/SKILL.md`, `tests/test_tasklist_check.py`, `tests/test_tasks_new_runtime.py`, `tests/test_qa_agent.py`, `tests/test_qa_exit_code.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - нормализовать `AIDD:TEST_EXECUTION` command schema для parser-safe downstream execution;
  - закрепить cwd-aware test execution в QA runtime и deterministic fail modes для command/path mismatch;
  - исключить non-canonical runtime recovery hints из stage handoff.
  **AC:** tasklist/QA используют единый canonical contract; hygiene/parser-only cases не становятся ложными blockers.
  **Deps:** W120-2
  **Regression/tests:** `python3 -m pytest -q tests/test_tasklist_check.py tests/test_tasks_new_runtime.py tests/test_qa_agent.py tests/test_qa_exit_code.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** Medium

- [x] **W120-7 (P0) Canonical workspace layout and runtime/hook write-safety enforcement** `skills/aidd-core/runtime/runtime.py`, `hooks/hooklib.py`, `hooks/context_gc/pretooluse_guard.py`, `tests/test_resources.py`, `tests/test_context_gc.py`, `tests/test_hook_rw_policy.py`, `tests/repo_tools/smoke-workflow.sh`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - разрешить runtime writes только в canonical `aidd/docs|reports|config|.cache`;
  - убрать auto-migration root-path behavior и вернуть deterministic bootstrap failure для uninitialized workspace;
  - синхронизовать runtime/hook path resolution на одном контракте.
  **AC:** full/smoke flow не мутирует non-canonical root paths вне `aidd/`.
  **Deps:** W120-2
  **Regression/tests:** `python3 -m pytest -q tests/test_resources.py tests/test_context_gc.py tests/test_hook_rw_policy.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** Medium

- [x] **W120-8 (P1) QA/report integrity and migration/workspace reconciliation edge-cases** `skills/qa/runtime/qa.py`, `skills/aidd-loop/runtime/loop_run.py`, `skills/tasks-new/runtime/tasks_new.py`, `hooks/gate-workflow.sh`, `skills/aidd-flow-state/runtime/stage_result.py`, `tests/test_qa_agent.py`, `tests/test_stage_result.py`, `tests/test_loop_run.py`, `tests/test_tasklist_check.py`:
  - синхронизовать QA `tests_executed` с фактическим исполнением и terminal outcome;
  - стабилизировать no-tests policy и migration/workspace reconciliation reason codes;
  - проверить cross-artifact integrity: tasklist -> review -> stage_result -> QA reports.
  **AC:** QA/report artifacts внутренне консистентны; migration/no-tests paths предсказуемы.
  **Deps:** W120-6, W120-7
  **Regression/tests:** `python3 -m pytest -q tests/test_qa_agent.py tests/test_stage_result.py tests/test_loop_run.py tests/test_tasklist_check.py`.
  **Effort:** M
  **Risk:** Medium

## Wave 121 — Prompt, Audit, and Replay Hygiene (2026-04-06)

_Статус: done (2026-04-09). Основание — устранение prompt-flow drift и audit noise после стабилизации core runtime, без изменения продуктовой логики внешних приложений._
_Evidence: `docs/runbooks/w120-w121-w136-closure.md`, `aidd/reports/events/w120-w121-w136-baseline-2026-04-09.md`._

- [x] **W121-1 (P1) `review-spec` payload-first source-of-truth + findings-sync convergence** `skills/aidd-core/runtime/prd_review.py`, `skills/aidd-core/runtime/prd_review_section.py`, `skills/review-spec/SKILL.md`, `skills/idea-new/runtime/analyst_check.py`, `skills/aidd-flow-state/runtime/prd_check.py`, `tests/test_prd_review_agent.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - вычислять narrative/recovery decisions только из structured report payload;
  - стабилизировать readiness findings-sync cycles для PRD/plan без stale deadlocks;
  - вернуть deterministic blocker, если convergence невозможен в bounded cycle.
  **AC:** review-spec decisions определяются structured payload; findings-sync сходится детерминированно.
  **Deps:** W120-2
  **Regression/tests:** `python3 -m pytest -q tests/test_prd_review_agent.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** High

- [x] **W121-2 (P1) Canonical prompt orchestration and runtime CLI contract** `skills/researcher/SKILL.md`, `skills/plan-new/SKILL.md`, `skills/tasks-new/SKILL.md`, `skills/implement/SKILL.md`, `skills/review/SKILL.md`, `skills/qa/SKILL.md`, `agents/researcher.md`, `agents/planner.md`, `agents/tasklist-refiner.md`, `agents/implementer.md`, `agents/qa.md`, `tests/test_prompt_lint.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - удалить non-canonical runtime hints/legacy handoff aliases как primary path;
  - закрепить только canonical runtime CLI args (`--scope-key`, `--work-item-key`, корректные stage commands);
  - запретить source-less derive/manual internals в top-level recovery guidance.
  **AC:** prompt surfaces не отправляют runner в non-canonical runtime/orchestration drift.
  **Deps:** W120-2
  **Regression/tests:** `python3 -m pytest -q tests/test_prompt_lint.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** Medium

- [x] **W121-3 (P1) Audit runner liveness + termination attribution + deterministic reason surfaces** `tests/repo_tools/aidd_stage_launcher.py`, `tests/repo_tools/aidd_stream_paths.py`, `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/aidd_audit_contract.py`, `tests/repo_tools/test_aidd_stage_launcher.py`, `tests/repo_tools/test_aidd_audit_runner.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - унифицировать stream-path extraction/fallback, не смешивая parser-noise и terminal causes;
  - детерминировать классификацию `watchdog_terminated`, `parent_terminated_or_external_terminate`, `scope_drift_recoverable`, `fallback_path_assembly_bug`, `repeated_command_failure_no_new_evidence`;
  - исключить ложные terminal transitions при active stream и валидном top-level payload.
  **AC:** audit runner выдаёт однозначный terminal/classification result для одинакового набора логов.
  **Deps:** W120-1, W120-4
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_aidd_stage_launcher.py tests/repo_tools/test_aidd_audit_runner.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** Medium

- [x] **W121-4 (P1) Write-safety/readiness telemetry normalization (noise suppression)** `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/test_aidd_audit_runner.py`, `tests/repo_tools/test_e2e_prompt_contract.py`, `tests/repo_tools/e2e_prompt/profile_full.md`:
  - развести pre-existing layout noise vs runtime write-safety breach;
  - подавить ложные `plugin_delta`/superseded readiness markers в итоговых status summaries;
  - оставить только actionable WARN/FAIL в terminal classification.
  **AC:** telemetry-noise не поднимает ложные blockers; реальная write-safety проблема остаётся видимой.
  **Deps:** W120-7, W121-3
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_aidd_audit_runner.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** S
  **Risk:** Medium

- [x] **W121-5 (P1) Replay fixtures for TST-001/TST-002 + parser edge-case hardening** `tests/fixtures/audit_tst001/*`, `tests/repo_tools/e2e_prompt/quality_profile_full.md`, `docs/e2e/aidd_test_quality_audit_prompt_tst002_full.txt`, `skills/tasks-new/runtime/tasks_new.py`, `skills/aidd-flow-state/runtime/tasklist_check.py`, `skills/aidd-flow-state/runtime/tasklist_normalize.py`, `skills/aidd-flow-state/runtime/prd_check.py`, `tests/test_tasks_new_runtime.py`, `tests/test_tasklist_check.py`, `tests/test_prd_ready_check.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - оформить воспроизводимые replay fixtures для критичных flow инцидентов;
  - стабилизировать parser edge cases, чтобы hygiene-only сигналы не превращались в terminal blocker;
  - ужесточить PRD parsing/cache invalidation без legacy bypass path.
  **AC:** ключевые TST-class инциденты воспроизводятся и детектируются в CI детерминированно.
  **Deps:** W121-3
  **Regression/tests:** `python3 -m pytest -q tests/test_tasks_new_runtime.py tests/test_tasklist_check.py tests/test_prd_ready_check.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** Medium

- [x] **W121-6 (P1) E2E prompt/runbook contract sync** `tests/repo_tools/e2e_prompt/profile_full.md`, `tests/repo_tools/e2e_prompt/quality_profile_full.md`, `docs/runbooks/tst001-audit-hardening.md`, `docs/e2e/aidd_test_flow_prompt_ralph_script_full.txt`, `docs/e2e/aidd_test_quality_audit_prompt_tst002_full.txt`:
  - синхронизовать документацию с фактическими runtime reason-codes и classification rules;
  - убрать расхождения между runbook/e2e profiles и текущим кодовым поведением;
  - закрепить единые определения terminal/non-terminal сигналов.
  **AC:** prompt/runbook surfaces не противоречат runtime/audit implementation.
  **Deps:** W121-3, W121-4
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py tests/repo_tools/test_e2e_quality_prompt_contract.py`.
  **Effort:** S
  **Risk:** Low

## Wave 136 — Integration Closure & Release Readiness (2026-04-06)

_Статус: done (2026-04-09). Основание — интеграционное закрытие после выполнения `Wave 120` и `Wave 121`; в этой волне нет самостоятельных runtime-переработок, только acceptance/release closure._
_Evidence: `docs/runbooks/w120-w121-w136-closure.md`, `aidd/reports/events/w120-w121-w136-baseline-2026-04-09.md`._

- [x] **W136-1 (P1) Full/smoke regression matrix for TST-001 and TST-002** `tests/repo_tools/smoke-workflow.sh`, `tests/repo_tools/test_e2e_prompt_contract.py`, `tests/repo_tools/test_e2e_quality_prompt_contract.py`, `tests/repo_tools/test_aidd_audit_runner.py`, `docs/runbooks/tst001-audit-hardening.md`:
  - зафиксировать regression matrix сценариев full/smoke для двух аудитов;
  - включить сценарии repeated bad command, non-canonical runtime drift, `exit_code=143` attribution, readiness/report mismatch;
  - добавить deterministic pass criteria для release gate.
  **AC:** regression matrix покрывает все критичные findings и проходит детерминированно.
  **Deps:** W120-8, W121-6
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py tests/repo_tools/test_e2e_quality_prompt_contract.py tests/repo_tools/test_aidd_audit_runner.py`.
  **Effort:** M
  **Risk:** Medium

- [x] **W136-2 (P1) Release-gate sign-off and CI required-check alignment** `.github/workflows/*`, `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/smoke-workflow.sh`, `docs/release-docs-manifest.yaml`, `docs/runbooks/marketplace-release.md`:
  - синхронизовать required checks с новой стабилизационной матрицей;
  - закрепить release sign-off критерии для flow integrity и audit determinism;
  - зафиксировать rollback criteria при regressions в seed/loop/qa flow.
  **AC:** release gate блокирует релиз при нарушении ключевых flow integrity критериев.
  **Deps:** W136-1
  **Regression/tests:** `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/smoke-workflow.sh`, `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py tests/repo_tools/test_e2e_quality_prompt_contract.py`.
  **Effort:** S
  **Risk:** Medium

- [x] **W136-3 (P2) Closure reporting, docs sync, and changelog finalization** `CHANGELOG.md`, `README.md`, `README.en.md`, `AGENTS.md`, `docs/backlog.md`, `docs/runbooks/tst001-audit-hardening.md`, `docs/runbooks/w120-w121-w136-closure.md`:
  - оформить closure report по выполненным findings и residual risks;
  - синхронизовать пользовательские/dev docs с итоговыми contracts;
  - зафиксировать release notes и postmortem links на regression evidence.
  **AC:** closure package завершён; документы и changelog соответствуют фактическому runtime behavior.
  **Deps:** W136-2
  **Regression/tests:** `tests/repo_tools/ci-lint.sh`, `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** S
  **Risk:** Low
