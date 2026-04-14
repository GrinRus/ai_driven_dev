# Product Backlog

> INTERNAL/DEV-ONLY: engineering wave planning and execution tracker.

Owner: feature-dev-aidd
Last reviewed: 2026-04-14
Status: active

_Revision note (2026-04-09): стабилизационный трек `120 -> 121 -> 136` закрыт (runtime/core -> prompt/audit -> integration closure). Волны `122..125` остаются roadmap-приоритетом._
_Priority note (2026-04-14): волны `123` и `122` закреплены как **самый низкий приоритет** до закрытия стабилизационных P0/P1 задач из активных волн._

## Archived Completed Waves

- Historical completed waves `120`, `121`, `136` moved to `docs/backlog-archive-w120-w121-w136.md`.
- Local evidence note: references like `aidd/reports/**` point to workspace-local artifacts and are not part of this git repository.

## Active Planned Waves

### Execution Queue (2026-04-14)

- Gate A (blocker-fixes before next full TST-001 rerun): `W145-2` -> `W145-1` -> `W137-1` -> `W137-2` -> `W137-3`.
- Gate B (de-noise/diagnostics right after Gate A): `W145-3`, `W139-1` -> `W139-3` -> `W139-5`, `W137-4`.
- Gate C (replay hardening after behavior fix): `W138-1` + (`W138-2`,`W138-3`,`W138-5`) -> `W138-6`; `W142-1` -> `W142-2`.
- Deferred feature-flags/rework tracks: `W143-*` only after Gate A/B stable in CI.
- Lowest priority roadmap (do not start before active stabilization closes): `W123-*` and `W122-*`.

## Wave 145 — TST-001 Run Findings Intake (2026-04-14)

_Статус: plan. Основание — full run `TST-001` (audit dir `20260413T191642Z`) дал terminal incidents: `06_implement` (`exit_code=143`, `killed=0`, `watchdog_marker=0`), `07_loop` (`blocked/actions_missing` из-за отсутствующего canonical review report), `08_qa` (`exit_code=1` + API `429`) при ложной `TELEMETRY_ONLY` классификации; также зафиксированы ложные WARN-сигналы `loop_runner_env_missing` и `workspace_layout_non_canonical_root_detected`._

- [ ] **W145-1 (P0) Review stage-result artifact atomicity guard** `skills/review/runtime/review_run.py`, `skills/aidd-loop/runtime/loop_step_stage_result.py`, `skills/aidd-flow-state/runtime/stage_result.py`, `tests/test_review_run.py`, `tests/test_loop_run.py`, `tests/test_stage_result.py`:
  - перед эмиссией `aidd.stage_result.v1` с `result=done` проверять существование `evidence_links.review_report` и соответствие path policy;
  - при отсутствии review report переводить stage в deterministic `blocked` (`reason_code=review_report_missing`) без записи `done`-result;
  - добавить replay fixture на кейс `stage.review.result.json` с битой ссылкой на report.
  **AC:** loop-step не может получить `done` stage-result review при отсутствующем canonical review report.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_review_run.py tests/test_loop_run.py tests/test_stage_result.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W145-2 (P0) Classification precedence: non-zero exit + top-level error must override telemetry-only** `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/aidd_stage_launcher.py`, `tests/repo_tools/test_aidd_audit_runner.py`, `tests/repo_tools/test_aidd_stage_launcher.py`, `tests/fixtures/audit_tst001/*`:
  - если `exit_code!=0` и есть top-level result/error payload (`is_error=true`), классифицировать run как terminal incident;
  - `stream_path_not_emitted_by_cli` оставлять только secondary telemetry;
  - добавить fixture для QA run с `429 rate_limit_error` и проверить корректный primary cause.
  **AC:** кейсы вроде `08_qa` с `exit_code=1` больше не попадают в `TELEMETRY_ONLY`.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_aidd_audit_runner.py tests/repo_tools/test_aidd_stage_launcher.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W145-3 (P1) `loop_runner_env_missing` detector hardening (init-only evidence)** `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/e2e_prompt/profile_full.md`, `tests/repo_tools/test_aidd_audit_runner.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - вычислять `loop_runner_env_missing` только по `init`-evidence (`permissionMode`, explicit approval-required events);
  - исключить noise из `tool_result`/artifact excerpts при определении env-misconfig;
  - добавить regression на кейс `permissionMode=bypassPermissions` + валидный plugin init.
  **AC:** false positive `ENV_MISCONFIG(loop_runner_env_missing)` не возникает при корректном non-interactive runner mode.
  **Deps:** W145-2
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_aidd_audit_runner.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** S
  **Risk:** Medium

## Wave 144 — Cleanup Signal Quality (2026-04-13)

_Статус: plan (deferred after run-stability gates). Основание — conservative cleanup показал ложноположительные `safe-to-delete` сигналы в repo topology audit для e2e prompt artifacts с indirect usage через генераторы и contract tests._

- [ ] **W144-1 (P1) Reduce false-positive `safe-to-delete` in topology audit** `tests/repo_tools/repo_topology_audit.py`, `tests/test_repo_topology_audit.py`, `tests/repo_tools/build_e2e_prompts.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - учесть indirect usage через glob/path-composition из генераторов и contract tests, чтобы `safe` triage не предлагал удалять реально используемые артефакты;
  - добавить protected-path heuristic для generated e2e prompt outputs;
  - добавить regression case для `docs/e2e/aidd_test_flow_prompt_ralph_script.txt`.
  **AC:** audit больше не маркирует используемые e2e prompt artifacts как `safe-to-delete`; regression test фиксирует кейс.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_repo_topology_audit.py tests/repo_tools/test_e2e_prompt_contract.py`, `python3 tests/repo_tools/repo_topology_audit.py --repo-root . --output-json /tmp/repo-revision.graph.json --output-md /tmp/repo-revision.md --output-cleanup /tmp/repo-cleanup-plan.json`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W144-2 (P2) Cleanup governance sync for generated report policy** `docs/revision/repo-revision.md`, `tests/repo_tools/repo_topology_audit.py`, `tests/test_repo_topology_audit.py`:
  - согласовать auto-triage `safe-to-delete` c текущей governance policy cleanup wave;
  - зафиксировать regression case, что active governance docs не попадают в `safe-to-delete` без явного archival decision.
  **AC:** generated revision report не конфликтует с принятой cleanup policy по active governance docs.
  **Deps:** W144-1
  **Regression/tests:** `python3 -m pytest -q tests/test_repo_topology_audit.py`, `python3 tests/repo_tools/repo_topology_audit.py --repo-root . --output-json /tmp/repo-revision.graph.json --output-md /tmp/repo-revision.md --output-cleanup /tmp/repo-cleanup-plan.json`.
  **Effort:** S
  **Risk:** Low

## Wave 143 — Soft/Strict Dual Classification Rework (planned)

_Статус: plan (deferred after W145/W137/W139). Цель — staged rollout dual-classification через feature-flag без изменения default verdict до стабилизации._

- [ ] **W143-1 (P0) Feature-flagged soft/strict classification** `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/aidd_audit_contract.py`, `tests/repo_tools/test_aidd_audit_runner.py`:
  - внедрить dual-classification только под явным флагом;
  - default режим оставить strict-compatible до завершения rollout.
  - execution note: не начинать до стабилизации `W145-2`, `W137-3`, `W139-5`.
  **AC:** без флага output не меняется; с флагом есть полная telemetry секция без влияния на default verdict.
  **Deps:** W145-2, W137-3, W139-5
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_aidd_audit_runner.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W143-2 (P1) Contract tests + prompt sync before rollout** `tests/repo_tools/test_e2e_prompt_contract.py`, `tests/repo_tools/test_e2e_quality_prompt_contract.py`, `tests/repo_tools/e2e_prompt/profile_full.md`, `tests/repo_tools/e2e_prompt/quality_profile_full.md`, `docs/e2e/*.txt`:
  - добавить contract/replay coverage до включения feature-flag по умолчанию;
  - синхронизировать prompt surface только после подтверждённой стабильности.
  **AC:** rollout защищён replay и contract-тестами до merge.
  **Deps:** W143-1
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py tests/repo_tools/test_e2e_quality_prompt_contract.py`.
  **Effort:** S
  **Risk:** Medium

## Wave 142 — Seed Convergence Rework (planned)

_Статус: plan (deferred after run-stability gates). Цель — пере-дизайн seed convergence без invasive runtime lock и без изменения default verdict._

- [ ] **W142-1 (P0) Non-invasive seed guard layer + compatibility mode** `skills/aidd-loop/runtime/preflight_prepare.py`, `skills/aidd-core/runtime/stage_actions_run.py`, `tests/test_preflight_prepare.py`, `tests/test_stage_actions_run.py`:
  - внедрить отдельный guard-слой с feature-flag/compat mode;
  - не менять canonical default path до подтверждения стабильности.
  **AC:** guard можно включать/выключать без изменения default поведения и без каскадных regressions.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_preflight_prepare.py tests/test_stage_actions_run.py`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W142-2 (P1) Replay fixtures before merge** `tests/fixtures/audit_tst001/*`, `tests/repo_tools/test_aidd_audit_runner.py`:
  - добавить replay fixtures до внедрения новой guard-логики;
  - зафиксировать expected verdict matrix для compatibility mode.
  **AC:** replay ловит regression до merge.
  **Deps:** W142-1
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_aidd_audit_runner.py`.
  **Effort:** S
  **Risk:** Medium

## Wave 139 — TST-001 Topology Guard & Audit Signal De-noise (2026-04-13)

_Статус: plan. Основание — TST-001 full run остановился на `tasks-new` из-за `ENV_MISCONFIG(cwd_wrong)` + `result_count=0`; дополнительно зафиксированы non-terminal WARN шумы (`review_spec_report_mismatch`, `tasklist_schema_parser_mismatch_recoverable`, `plugin_write_safety_inconclusive`, `workspace_layout_non_canonical_root_detected`, `readiness_gate_research_softened`)._

- [ ] **W139-1 (P0) Topology invariant hard-stop + canonical launcher parity** `tests/repo_tools/aidd_stage_launcher.py`, `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/e2e_prompt/profile_full.md`, `tests/repo_tools/e2e_prompt/quality_profile_full.md`, `tests/repo_tools/test_aidd_stage_launcher.py`, `tests/repo_tools/test_aidd_audit_runner.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - enforce pre-run invariant `realpath(PROJECT_DIR) != realpath(PLUGIN_DIR)` до первого stage-run и на каждом retry;
  - запретить обход canonical launcher в audit workflow;
  - при нарушении topology завершать аудит terminal `ENV_MISCONFIG(cwd_wrong)` без каскадного запуска шагов.
  **AC:** при `PROJECT_DIR==PLUGIN_DIR` аудит останавливается до stage sequence; нет downstream ложных причин.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_aidd_stage_launcher.py tests/repo_tools/test_aidd_audit_runner.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W139-2 (P0) tasks-new bounded cwd_wrong recovery + guaranteed terminal top-level result** `skills/tasks-new/SKILL.md`, `skills/tasks-new/runtime/tasks_new.py`, `tests/test_tasks_new_runtime.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - при `refusing to use plugin repository as workspace root` выполнять не более 1 корректного retry;
  - исключить длительные debug/edit side-loops после env blocker;
  - обеспечить deterministic terminal payload вместо `result_count=0` path.
  **AC:** `tasks-new` при `cwd_wrong` завершает run прозрачным terminal outcome; нет `result_count=0` без top-level result.
  **Deps:** W139-1
  **Regression/tests:** `python3 -m pytest -q tests/test_tasks_new_runtime.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W139-3 (P1) review-spec mismatch de-noise for READY/0 findings** `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/test_aidd_audit_runner.py`, `tests/repo_tools/e2e_prompt/profile_full.md`, `tests/repo_tools/e2e_prompt/quality_profile_full.md`:
  - при `recommended_status=ready`, `findings_count=0`, `open_questions_count=0` классифицировать narrative mismatch как non-blocking info;
  - убрать promotion такого кейса в prompt-exec incident.
  **AC:** `review_spec_report_mismatch` в READY-clean кейсе не повышается выше INFO.
  **Deps:** W139-1
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_aidd_audit_runner.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W139-4 (P1) Tasklist test-execution schema parity (`tasks` vs `commands`)** `skills/aidd-flow-state/runtime/tasklist_check.py`, `skills/tasks-new/runtime/tasks_new.py`, `skills/tasks-new/templates/tasklist.template.md`, `tests/test_tasklist_check.py`, `tests/test_tasks_new_runtime.py`, `tests/test_qa_agent.py`:
  - считать `tasks_list_count>0` валидным executable contract без обязательного `commands` ключа;
  - синхронизовать parser/probe/runtime чтобы не генерировать ложный `WARN(tasklist_schema_parser_mismatch_recoverable)`.
  **AC:** валидный `AIDD:TEST_EXECUTION` больше не поднимает parser mismatch WARN.
  **Deps:** W139-2
  **Regression/tests:** `python3 -m pytest -q tests/test_tasklist_check.py tests/test_tasks_new_runtime.py tests/test_qa_agent.py`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W139-5 (P1) Classification precedence + workspace-layout profile under upstream env blocker** `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/aidd_stage_launcher.py`, `tests/repo_tools/test_aidd_audit_runner.py`, `tests/repo_tools/e2e_prompt/profile_full.md`, `docs/runbooks/tst001-audit-hardening.md`:
  - если primary причина шага = `ENV_MISCONFIG(cwd_wrong)`, downstream `plugin_write_safety_inconclusive`/`workspace_layout_non_canonical_root_detected` помечать как secondary telemetry;
  - убрать ошибочную эскалацию release-risk при topology misconfig run.
  - ввести repo-aware allowlist/profile для root-level директорий (включая `./docs`) в workspace layout check;
  - синхронизовать runbook с новой policy layout/precedence.
  **AC:** итоговая классификация сохраняет одну primary причину и не дублирует terminal шум.
  **Deps:** W139-1, W139-3, W145-2
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_aidd_audit_runner.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W139-6 (P1) Preflight artifact completeness and source-of-truth alignment** `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/e2e_prompt/profile_full.md`, `tests/repo_tools/e2e_prompt/quality_profile_full.md`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - всегда создавать `01_gates_snapshot.json` и `01_test_policy_source_scan.txt` (или `not_available` marker);
  - явно фиксировать, что source-of-truth plugin load = `init` payload, а `claude plugin list` — supplementary telemetry.
  **AC:** preflight evidence deterministic и полный в каждом run.
  **Deps:** W139-1
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py tests/repo_tools/test_aidd_audit_runner.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W139-7 (P2) Readiness softened signal normalization for minimal RLM baseline** `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/e2e_prompt/profile_full.md`, `tests/repo_tools/test_aidd_audit_runner.py`, `tests/test_gate_workflow.py`:
  - при baseline-complete research (`targets/manifest/worklist/pack + non-empty nodes`) переводить `WARN(readiness_gate_research_softened)` в `INFO`;
  - сохранить текущую non-terminal policy без изменения hard-block rules.
  **AC:** expected soft-readiness не засоряет WARN-канал, но остаётся видимым в telemetry.
  **Deps:** W139-6
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_aidd_audit_runner.py tests/test_gate_workflow.py`.
  **Effort:** S
  **Risk:** Low

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

- [ ] **W137-3 (P0) Exit-143 attribution normalization and watchdog precedence** `skills/aidd-loop/runtime/loop_run_parts/core.py`, `tests/test_loop_run.py`, `tests/repo_tools/test_aidd_audit_runner.py`, `tests/repo_tools/test_aidd_stage_launcher.py`, `tests/fixtures/audit_tst001/*`, `docs/runbooks/tst001-audit-hardening.md`:
  - унифицировать ветку классификации `exit_code=143` по watchdog-marker/killed semantics;
  - исключить ambiguous mapping, когда termination интерпретируется не тем классом причины;
  - выровнять runtime vs audit tooling reason precedence.
  - добавить replay/diagnostics для external terminate path (`exit_code=143`, `killed_flag=0`, `watchdog_marker=0`) с обязательным attribution evidence.
  **AC:** `exit_code=143` классифицируется однозначно и повторяемо (watchdog vs external terminate) в runtime и audit runner.
  **Deps:** W137-2
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_run.py tests/repo_tools/test_aidd_audit_runner.py tests/repo_tools/test_aidd_stage_launcher.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W137-4 (P1) Stream-path missing telemetry hardening for liveness/stall** `tests/repo_tools/aidd_stage_launcher.py`, `tests/repo_tools/aidd_stream_paths.py`, `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/test_aidd_stage_launcher.py`, `tests/repo_tools/test_aidd_audit_runner.py`:
  - при `stream_path_not_emitted_by_cli` не повышать сигнал до terminal сам по себе;
  - подтверждать stall только при отсутствии роста и main log, и валидных stream/event источников;
  - расширить diagnostics, чтобы parser-noise не маскировал primary причину stage-failure.
  - scope note: non-zero exit precedence для top-level error вынесен в `W145-2`, чтобы избежать пересечения rule-sets.
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

## Rolled Back Waves

## Wave 140 — TST-001 Implement Seed Convergence & Budget Attribution (2026-04-13)

_Статус: rolled back (2026-04-13). Основание — surgical rollback wave 140/141 после анализа TST-001: изменения возвращены к pre-wave140/141 модели с сохранением wave139 topology/de-noise._

- [ ] **W140-1 (P0) Implement seed single-scope hard-stop + guaranteed terminal result (reverted)** `skills/implement/runtime/implement_run.py`, `skills/aidd-core/runtime/stage_actions_run.py`, `skills/aidd-flow-state/runtime/stage_result.py`, `tests/test_implementer_prompt.py`, `tests/test_stage_result.py`:
  - запретить cascade `I1 -> I2` внутри одного seed-run;
  - при попытке scope drift эмитить canonical terminal payload (`blocked`, reason=`seed_scope_cascade_detected`) вместо бесконечного продолжения.
  **AC:** после `iteration_id_I1` terminal outcome run завершается и не создаёт `iteration_id_I2` preflight в том же запуске; `top_level_result=1`.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_implementer_prompt.py tests/test_stage_result.py tests/test_stage_actions_run.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W140-2 (P0) Canonical launcher budget watchdog with deterministic attribution (reverted)** `tests/repo_tools/aidd_stage_launcher.py`, `tests/repo_tools/test_aidd_stage_launcher.py`, `tests/repo_tools/e2e_prompt/profile_full.md`:
  - добавить launcher-level budget (`--budget-seconds`) на monotonic clock;
  - при budget kill писать `*_termination_attribution.txt` с `killed_flag=1`, `watchdog_marker=1`, `stage_elapsed_seconds`, `signal`.
  **AC:** budget termination воспроизводится одинаково и не зависит от внешнего kill; attribution файл всегда присутствует.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_aidd_stage_launcher.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W140-3 (P0) Rollup parity: classify with sibling termination/liveness artifacts (reverted)** `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/test_aidd_audit_runner.py`, `tests/fixtures/audit_tst001/*`:
  - в `rollup` режиме автоматически подхватывать `*_termination_attribution.txt`, `*_stream_liveness_check*.txt`, `05_precondition_block.txt`;
  - не классифицировать только по summary.
  **AC:** для `06_implement` rollup совпадает с per-run classify (`watchdog_terminated` при `killed=1/watchdog_marker=1`).
  **Deps:** W140-2
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_aidd_audit_runner.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W140-4 (P1) Implement test-env fail-fast (dependency missing) без budget burn (reverted)** `skills/implement/SKILL.md`, `agents/implementer.md`, `skills/implement/runtime/implement_run.py`, `tests/test_implementer_prompt.py`:
  - при deterministic ошибках окружения (пример: Playwright browser missing) завершать stage canonical blocked-result с reason=`tests_env_dependency_missing`;
  - исключить повторные install loops в одном run.
  **AC:** нет длительного повтора `playwright install`/аналогов; terminal result появляется сразу после подтверждённой env ошибки.
  **Deps:** W140-1
  **Regression/tests:** `python3 -m pytest -q tests/test_implementer_prompt.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W140-5 (P1) Step6 contract hardening: one manual implement/review pair without cross-iteration spill (reverted)** `tests/repo_tools/e2e_prompt/profile_full.md`, `tests/repo_tools/e2e_prompt/quality_profile_full.md`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - явно зафиксировать в prompt-contract, что `implement` seed-run не имеет права переключать work_item;
  - следующий item только через loop orchestration.
  **AC:** prompt-contract тесты проверяют anti-cascade правило и терминальные reason-codes.
  **Deps:** W140-1
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py tests/repo_tools/test_e2e_quality_prompt_contract.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W140-6 (P2) Replay fixture for this incident (I1 done + I2 drift + watchdog kill) (reverted)** `tests/fixtures/audit_tst001/*`, `tests/repo_tools/test_aidd_audit_runner.py`, `docs/runbooks/tst001-audit-hardening.md`:
  - добавить fixture и проверку primary-cause precedence.
  **AC:** CI воспроизводит сценарий и ловит regression по drift/attribution.
  **Deps:** W140-3
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_aidd_audit_runner.py`.
  **Effort:** S
  **Risk:** Low

## Wave 141 — TST-001 Soft-by-default Diagnostics + Implement Convergence Hard-stop (2026-04-13)

_Статус: rolled back (2026-04-13). Основание — rollback wave 140/141: soft-default/strict-shadow и single-scope hard-stop убраны из active policy surface._

- [ ] **W141-1 (P0) Implement seed single-scope hard-stop in preflight/runtime chain (reverted)** `skills/aidd-loop/runtime/preflight_prepare.py`, `tests/test_preflight_prepare.py`:
  - enforce stage-run lock in preflight path (`AIDD_STAGE_RUN_LOCK_ID`) для implement seed;
  - при cross-iteration попытке эмитить canonical blocked preflight with `reason_code=seed_scope_cascade_detected`.
  **AC:** cross-iteration drift в одном seed-run детерминированно блокируется с canonical reason-code.
  **Deps:** W140-1
  **Regression/tests:** `python3 -m pytest -q tests/test_preflight_prepare.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W141-2 (P0) Soft-default classification profile + strict-shadow telemetry (reverted)** `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/test_aidd_audit_runner.py`:
  - добавить `classification_profile=soft_default|strict` (default `soft_default`);
  - для `06_implement` soft profile понижает terminal implement blockers в `WARN`;
  - всегда сохранять strict-shadow поля: `strict_shadow_classification`, `primary_root_cause`, `softened`, `softened_from`, `softened_to`.
  **AC:** soft verdict продолжает downstream сигнал, strict-shadow сохраняет root-cause без потерь.
  **Deps:** W140-3
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_aidd_audit_runner.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W141-3 (P1) Prompt-contract hardening for soft-default + strict-shadow (reverted)** `tests/repo_tools/e2e_prompt/profile_full.md`, `tests/repo_tools/e2e_prompt/quality_profile_full.md`, `tests/repo_tools/test_e2e_prompt_contract.py`, `tests/repo_tools/test_e2e_quality_prompt_contract.py`, `docs/e2e/*.txt`:
  - зафиксировать `CLASSIFICATION_PROFILE=soft_default|strict`;
  - добавить правило soft-default continuation для шага 6 и strict-shadow telemetry block;
  - синхронизировать generated prompt outputs.
  **AC:** prompt contract и generated outputs согласованы с dual-profile policy.
  **Deps:** W141-2
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py tests/repo_tools/test_e2e_quality_prompt_contract.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W141-4 (P2) Runbook updates for soft PASS + strict FAIL interpretation (reverted)** `docs/runbooks/tst001-audit-hardening.md`:
  - документировать policy и triage для dual verdict mode;
  - добавить guidance по manual strict rerun/escalation.
  **AC:** runbook объясняет, как читать `soft PASS` вместе с strict-shadow failure.
  **Deps:** W141-2
  **Regression/tests:** docs-only.
  **Effort:** S
  **Risk:** Low
