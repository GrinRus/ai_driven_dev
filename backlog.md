# Product Backlog

## Wave 108 — TST-001 e2e flow remediation (run `20260309T070354Z`)

_Статус: план. Цель — закрыть WARN/blocked-сигналы из full-аудита `TST-001` (run: `20260309T070354Z`) и вернуть детерминированную сходимость full-profile без non-canonical drift._

Evidence baseline:
- `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-001/20260309T070354Z/05_plan_new_drift_check.txt`
- `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-001/20260309T070354Z/05_review_spec_report_check_run1.txt`
- `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-001/20260309T070354Z/05_review_spec_report_check_run4.txt`
- `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-001/20260309T070354Z/07_loop_run1.log`
- `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-001/20260309T070354Z/07_loop_run1.summary.txt`
- `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-001/20260309T070354Z/07_scope_mismatch_check.txt`
- `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-001/20260309T070354Z/07_recoverable_block_policy_check.txt`
- `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-001/20260309T070354Z/07_loop_stream_liveness_check.txt`

- [ ] **W108-1 (P0)** Remove plan-stage runtime drift to non-canonical/missing `set_stage.py` (`skills/plan-new/SKILL.md`, `agents/planner.md`, `skills/plan-new/runtime/*`, `tests/repo_tools/test_e2e_prompt_contract.py`):
  - убрать обращения к `skills/aidd-flow-state/runtime/set_stage.py` и legacy summary path, оставить только canonical `set_active_stage.py`/stage routing;
  - добавить tripwire-тест на сигнатуру `can't open file ... set_stage.py`.
  **AC:** в `plan-new` run-логах отсутствуют nested `set_stage.py` ошибки; stage завершает top-level result без runtime path drift.

- [ ] **W108-2 (P0)** Enforce review-spec source-of-truth alignment (report payload first) (`skills/review-spec/**`, `skills/review-spec/runtime/*`, `tests/test_review_spec.py`, `tests/repo_tools/test_e2e_prompt_contract.py`):
  - синхронизовать top-level narrative с `aidd/reports/prd/<ticket>.json|*.pack.json`;
  - при расхождении выставлять явный telemetry marker и deterministic next action по report payload.
  **AC:** `narrative_vs_report_mismatch=0` на happy-path rerun; решение readiness/sync принимается только из report payload.

- [ ] **W108-3 (P0)** Loop scope reconciliation for next-iteration review (`skills/aidd-loop/runtime/loop_step_parts/core.py`, `skills/aidd-loop/runtime/loop_run_parts/core.py`, `tests/test_loop_step.py`, `tests/test_loop_run.py`):
  - устранить fallback `expected_scope_key=iteration_id_I2` -> `selected_scope_key=iteration_id_I1` как default path;
  - закрепить deterministic reconcile/probe path для `scope_key_mismatch_warn` без неявного stale fallback.
  **AC:** в loop-step для `iteration_id_I2` отсутствует `scope_key_mismatch_warn`; stage-result candidate выбирается по authoritative scope.

- [ ] **W108-4 (P0)** Ralph recoverable retry convergence for `no_tests_hard` in review stage (`skills/review/runtime/*`, `skills/aidd-loop/runtime/loop_run_parts/core.py`, `skills/aidd-flow-state/runtime/*`, `tests/test_review_agent.py`, `tests/test_loop_run.py`):
  - обеспечить детерминированное формирование tests evidence для `iteration_id_I<N>` в recoverable path `handoff_to_implement`;
  - исключить terminal blocked по `no_tests_hard` при валидно выполненном recoverable retry budget.
  **AC:** loop-run в `BLOCKED_POLICY=ralph` после recoverable retries не завершается `reason_code=no_tests_hard` на том же ticket при наличии ожидаемого tests evidence.

- [ ] **W108-5 (P1)** Output-contract warning cleanup for loop-step artifacts (`skills/aidd-loop/runtime/output_contract.py`, `skills/aidd-loop/runtime/loop_step_stage_chain.py`, `tests/test_loop_step.py`):
  - закрыть `output_contract_warn(read_log_missing, read_order_missing_loop_pack)` в штатном path;
  - гарантировать порядок и наличие read-order/loop-pack артефактов до финального blocked/done return.
  **AC:** loop-step happy/recoverable path не генерирует `read_log_missing`/`read_order_missing_loop_pack` warnings.

- [ ] **W108-6 (P1)** Audit/telemetry parser hardening for stream path normalization (`tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/test_aidd_audit_runner.py`):
  - корректно парсить `stream=... log=...` токены из loop stdout без ложных `stream_path_missing` префиксов;
  - сохранить source-attribution (`raw|metadata|fallback_scan`) и фильтрацию path outside workspace.
  **AC:** stream-path report не содержит артефактных путей вида `.../stream=aidd/...`; liveness набор состоит из нормализованных валидных workspace paths.

- [ ] **W108-7 (P1)** Full-profile regression guard for run `20260309T070354Z` signatures (`tests/repo_tools/test_e2e_prompt_contract.py`, `tests/repo_tools/smoke-workflow.sh`, `tests/repo_tools/ci-lint.sh`):
  - добавить проверки на сигнатуры: plan `set_stage.py` drift, review-spec mismatch, loop scope mismatch fallback, terminal `no_tests_hard` after ralph retries, output_contract_warn;
  - зафиксировать expected/allowed WARN matrix отдельно от terminal blockers.
  **AC:** регрессии из run `20260309T070354Z` воспроизводимо ловятся в repo-tools до merge.

## Wave 107 — TST-001 e2e flow remediation (run `20260308T093331Z`)

_Статус: план. Цель — закрыть причины WARN/FAIL из full-аудита `TST-001` (run: `20260308T093331Z`) и получить детерминированную сходимость без ручного/не-canonical recovery path._

Evidence baseline:
- `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-001/20260308T093331Z/05_precondition_block.txt`
- `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-001/20260308T093331Z/05_tasks_new_run1.log`
- `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-001/20260308T093331Z/06_implement_run1.log`
- `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-001/20260308T093331Z/06_implement_silent_stall_diagnostics.txt`
- `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-001/20260308T093331Z/07_loop_result_payload.json`
- `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-001/20260308T093331Z/08_qa_run1.log`
- `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/aidd/reports/qa/TST-001-qa-findings.json`

- [ ] **W107-1 (P0)** Researcher convergence for `links_empty_warn` + non-empty context content (`skills/researcher/runtime/research.py`, `skills/aidd-rlm/runtime/rlm_links_build.py`, `skills/researcher/templates/research.template.md`, `tests/test_research_command.py`):
  - убрать деградацию research summary в массовые `TBD` при наличии baseline RLM artifacts;
  - стабилизировать `no_symbols` path: детерминированная диагностика what/why + bounded fallback на symbol sources;
  - сохранить soft-readiness semantics, но с содержательным `AIDD:CONTEXT_PACK`/`AIDD:INTEGRATION_POINTS`.
  **AC:** после `researcher --auto` research-doc не содержит placeholder-`TBD` в ключевых секциях; `links_empty_warn` остаётся telemetry, а не content collapse.

- [ ] **W107-2 (P0)** Remove tasks-new runtime CLI drift (`progress_cli --message`) (`skills/tasks-new/SKILL.md`, `agents/tasklist-refiner.md`, `skills/tasks-new/runtime/tasks_new.py`, `tests/test_tasks_new.py`, `tests/repo_tools/test_e2e_prompt_contract.py`):
  - запретить non-canonical аргументы для `progress_cli.py` в prompt/runtime path;
  - зафиксировать canonical вызов `progress_cli.py` без `--message`;
  - добавить drift tripwire в e2e prompt contract tests.
  **AC:** в `tasks-new` stage logs отсутствуют `progress_cli.py: error: unrecognized arguments: --message`; stage завершает top-level result без nested contract mismatch.

- [ ] **W107-3 (P0)** Implement-stage command-exec fail-fast for `command_not_found` loops (`skills/implement/runtime/implement_run.py`, `skills/implement/SKILL.md`, `agents/implementer.md`, `tests/test_implement_agent.py`, `tests/test_loop_step.py`):
  - обнаруживать повторяющийся `Exit code 127`/`no such file or directory` (например, `./gradlew`) как terminal prompt-exec incident, а не продолжать long-running попытки;
  - нормализовать тестовые команды на cwd-aware pattern (`backend/gradlew` when needed);
  - обеспечить явный reason_code и canonical next action вместо silent convergence.
  **AC:** implement stage не уходит в silent stall на повторяющемся `command_not_found`; при таком кейсе возвращает детерминированный terminal payload в рамках budget.

- [ ] **W107-4 (P0)** Loop scope reconciliation + diff-boundary attribution hardening (`skills/aidd-loop/runtime/loop_step_parts/core.py`, `skills/aidd-loop/runtime/loop_run_parts/core.py`, `skills/aidd-docio/runtime/actions_apply.py`, `tests/test_loop_step.py`, `tests/test_loop_run.py`):
  - устранить `scope_key_mismatch_warn` в happy path (authoritative scope selection consistency);
  - в `diff_boundary_violation` учитывать pre-existing/base diff attribution, чтобы не смешивать текущие изменения итерации с посторонними;
  - оставить `FORBIDDEN`/реальные boundary нарушения terminal по policy.
  **AC:** при валидном scope loop не генерирует mismatch warning; boundary block содержит корректную attribution текущей итерации и не срабатывает из-за чужого/stale diff.

- [ ] **W107-5 (P1)** Loop-run telemetry parity for python launcher (`tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/test_aidd_audit_runner.py`, `tests/repo_tools/e2e_prompt/profile_full.md`):
  - синхронизовать summary parser с nested stream/init evidence для `loop_run.py` path;
  - исключить ложные `init_present=0/plugin_loaded=0` при валидном stream result.
  **AC:** summary-файлы loop-run отражают корректные init/plugin markers при python launcher execution.

- [ ] **W107-6 (P1)** QA stage-result reason semantics for blocked findings (`skills/qa/runtime/qa_parts/core.py`, `skills/qa/runtime/qa.py`, `skills/aidd-flow-state/runtime/stage_result.py`, `tests/test_qa_agent.py`, `tests/test_qa_exit_code.py`):
  - для blocked QA findings выставлять canonical `reason_code=blocking_findings` (вместо пустого reason_code);
  - сохранить `schema=aidd.stage_result.v1` и evidence links contract.
  **AC:** `stage.qa.result.json` при blocked findings содержит непустой canonical reason_code; downstream loop/policy однозначно классифицируют блокировку.

- [ ] **W107-7 (P1)** Full-profile regression suite for TST-001 WARN/FAIL signatures (`tests/repo_tools/test_e2e_prompt_contract.py`, `tests/repo_tools/smoke-workflow.sh`, `tests/repo_tools/ci-lint.sh`):
  - добавить контрактные проверки на сигнатуры run `20260308T093331Z`: `progress_cli --message`, repeated `exit 127` loops, scope mismatch drift, empty QA reason_code;
  - зафиксировать expected soft-warn only behavior для scoped research warn path.
  **AC:** регрессии класса TST-001 (run 20260308) воспроизводимо ловятся в repo-tools до merge.

## Wave 104 — TST-001 e2e flow remediation (WARN/FAIL closure)

_Статус: план. Цель — закрыть причины WARN/FAIL из full-аудита `TST-001` (run: `20260307T172536Z`) и получить детерминированный PASS на full profile без ручных recovery path._

Evidence baseline:
- `<workspace>/.aidd_audit/TST-001/20260307T172536Z/05_plan_new_run1.log`
- `<workspace>/.aidd_audit/TST-001/20260307T172536Z/06_review_run1.log`
- `<workspace>/.aidd_audit/TST-001/20260307T172536Z/07_loop_run_run1.log`
- `<workspace>/.aidd_audit/TST-001/20260307T172536Z/08_qa_run1.log`
- `<workspace>/.aidd_audit/TST-001/20260307T172536Z/05_precondition_block_initial.txt`
- `<workspace>/.aidd_audit/TST-001/20260307T172536Z/05_precondition_block.txt`

- [ ] **W104-1 (P0)** Eliminate planner drift to missing runtime entrypoint (`set_stage.py`) in plan-stage orchestration (`skills/plan-new/**`, prompts/runtime handoff text):
  - убрать/нормализовать все вызовы несуществующего `skills/aidd-flow-state/runtime/set_stage.py`;
  - использовать только canonical `set_active_stage.py` interface при необходимости.
  **AC:** в `plan-new` run-логах отсутствуют `can't open file .../set_stage.py`; top-level stage остаётся `exit_code=0` без nested runtime path errors.

- [ ] **W104-2 (P0)** Stage-result enum contract hardening for review/qa (`skills/review/**`, `skills/qa/**`, shared stage_result writers/tests):
  - запретить передачу non-canonical `--result` значений (`revise_required`, `conditional_pass`) в `stage_result.py`;
  - ввести явное mapping-правило user-facing verdict -> canonical result (`blocked|continue|done`) до вызова runtime.
  **AC:** в review/qa логах нет `stage_result.py: error: argument --result: invalid choice`; stage-result artifacts всегда валидны с первой попытки.

- [ ] **W104-3 (P1)** Readiness recovery telemetry convergence (`tests/repo_tools/e2e_prompt/*`, audit harness scripts, reporting helpers):
  - после recovery `readiness_gate=PASS` автоматически помечать ранние `*_skipped_*`/`05_gate_outcome` как superseded в едином итоговом status file;
  - исключить ложный terminal narrative при фактическом downstream execution.
  **AC:** итоговый audit status по шагу 5 не содержит конфликтующих `NOT VERIFIED` при реально выполненных `5.3/5.4/5.5`.

- [ ] **W104-4 (P1)** Ralph loop policy improvement for diff-boundary hard blocks (`skills/aidd-loop/runtime/loop_*`, boundary policy config/tests):
  - разобрать `diff_boundary_violation` кейс `out_of_scope=26 threshold=25` на implement loop-step;
  - добавить policy-safe recovery/telemetry path для near-threshold кейсов без ослабления `FORBIDDEN`.
  **AC:** `BLOCKED_POLICY=ralph` не падает terminal на near-threshold boundary cases без попытки policy-defined recovery, при этом `FORBIDDEN` остаётся terminal.

- [ ] **W104-5 (P1)** Loop scope/output-contract warning cleanup (`skills/aidd-loop/runtime/loop_run_parts/*`, `output_contract.py`, tests):
  - убрать предупреждения `scope_key_mismatch_warn` fallback-перехода и `output_contract_warn(read_log_missing, read_order_missing_loop_pack)` в happy path;
  - обеспечить консистентный preflight/read-order для loop pack/report logs.
  **AC:** на full-flow smoke отсутствуют вышеуказанные WARN при валидном env и canonical artifacts.

- [ ] **W104-6 (P1)** Add TST-001 regression checks to repo tools (`tests/repo_tools/**`, smoke/e2e profiles):
  - автоматические проверки на: missing runtime path drift, invalid stage_result enum usage, stale readiness telemetry conflicts, loop hard-block attribution;
  - включить в `ci-lint.sh`/smoke profile как non-flaky contract guard.
  **AC:** регрессии класса TST-001 ловятся автоматически до merge.

## Wave 103 — Runtime bootstrap hardening + stale cache rollout

_Статус: план. Цель — полностью закрыть `ModuleNotFoundError: No module named 'aidd_runtime'` в direct runtime path (cache/install) и исключить регрессии._

- [ ] **W103-1 (P0)** Runtime bootstrap completion for remaining entrypoints (`skills/aidd-core/runtime/research_guard.py`, `skills/aidd-docio/runtime/context_expand.py`, `skills/aidd-flow-state/runtime/progress.py`, `skills/aidd-loop/runtime/preflight_prepare.py`, `skills/aidd-observability/runtime/doctor.py`, `skills/aidd-rlm/runtime/rlm_finalize.py`, `skills/aidd-rlm/runtime/rlm_links_build.py`):
  - гарантировать self-bootstrap `CLAUDE_PLUGIN_ROOT`/`sys.path` до первого `from aidd_runtime ...`;
  - не менять бизнес-логику модулей.
  **AC:** `python3 -S <entrypoint> --help` проходит из внешнего cwd без `CLAUDE_PLUGIN_ROOT`/`PYTHONPATH`.

- [ ] **W103-2 (P0)** Runtime bootstrap CI guard (`tests/repo_tools/runtime-bootstrap-guard.py`) + wiring in repo tools (`tests/repo_tools/ci-lint.sh`, `tests/repo_tools/python-only-regression.sh`):
  - автоматический проход по `skills/*/runtime/*.py` с `__main__`;
  - fail на любом non-zero/`ModuleNotFoundError`.
  **AC:** регрессии bootstrap ловятся в CI до merge.

- [ ] **W103-3 (P0)** Plugin version bump + stale-cache rollout playbook (`.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `README.md`, `README.en.md`):
  - bump plugin version для cache invalidation;
  - операторская процедура remove/install + session restart.
  **AC:** после update/reinstall новый cache не воспроизводит runtime bootstrap ошибку.

- [ ] **W103-4 (P1)** E2E/audit probe hardening (`tests/repo_tools/e2e_prompt/profile_full.md`, `tests/repo_tools/e2e_prompt/profile_smoke.md`, `docs/runbooks/tst001-audit-hardening.md`):
  - bootstrap probes в изолированном режиме `python3 -S`;
  - явная фиксация, что site-packages не должны маскировать дефект.
  **AC:** audit prompts и runbook детерминированно воспроизводят/детектят bootstrap gaps.

- [ ] **W103-5 (P1)** Contract cleanup for release notes (`CHANGELOG.md`):
  - убрать некорректную формулировку про "all risk runtime entrypoints hardened";
  - зафиксировать завершение coverage и новые guard-инварианты.
  **AC:** changelog не расходится с фактическим runtime state.

## Wave 102 — Loop soft-gate for Research (temporary)

_Статус: план. Цель — не блокировать loop на `research_status_invalid` во время стабилизации research, затем вернуть строгий gate после исправлений._

- [ ] **W102-1** Stabilize Researcher/RLM links for `no_symbols` cases (`skills/aidd-rlm/runtime/rlm_links_build.py`, `skills/researcher/runtime/research.py`, `tests/test_rlm_links_build.py`, `tests/test_research_command.py`):
  - снизить ложные `links_empty_reason=no_symbols` на реальных backend/frontend кодовых базах;
  - добавить диагностику (какие target files/symbol sources отброшены и почему).
  **AC:** на репрезентативных тикетах `research --auto` перестаёт массово застревать в `Status: warn` из-за `no_symbols`.

- [ ] **W102-2** Add observability for loop research soft-gate usage (`skills/aidd-loop/runtime/loop_run_parts/core.py`, `tests/test_loop_run.py`):
  - фиксировать отдельный telemetry marker для soft-continue на `research_status_invalid`;
  - добавить сводный отчёт частоты soft-gate с reason codes в loop artifacts.
  - Findings (2026-03-03): в policy probe `qa_tests_failed` `ralph` корректно маркирует `recoverable_blocked=1`, `retry_attempt=1`, `recovery_path=handoff_to_implement`; `strict` остаётся terminal blocked (`recoverable_blocked=0`).
    Evidence: `.aidd_audit/loop_policy/20260303T080709Z/findings_summary_20260303.md`.
  **AC:** по логам/pack можно детерминированно увидеть, где loop стартовал через soft-gate.

- [ ] **W102-3** Return strict research gate after stabilization (`skills/aidd-loop/runtime/loop_run_parts/core.py`, `templates/aidd/config/gates.json`, `tests/test_loop_run.py`, `tests/repo_tools/e2e_prompt/profile_full.md`):
  - вернуть fail-fast блокировку `research_status_invalid` (через policy/config flag + rollout plan);
  - обновить e2e prompt contract и smoke/regression проверки.
  - Findings (2026-03-03): для non-recoverable причины (`review_pack_missing`) `strict` и `ralph` дают одинаковый terminal blocked (retry не запускается); rollback-план должен явно разделять recoverable/non-recoverable reason classes.
    Evidence: `.aidd_audit/loop_policy/20260303T080709Z/findings_summary_20260303.md`, `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/aidd/reports/loops/TST-001/cli.loop-run.20260303-080259.log`, `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/aidd/reports/loops/TST-001/cli.loop-run.20260303-080315.log`.
  **AC:** strict mode снова блокирует loop при неконсистентном research; есть подтверждённый rollout toggle и тесты.

- [ ] **W102-5** Keep loop scope-mismatch as non-terminal telemetry for post-review iteration rework (`skills/aidd-loop/runtime/loop_step_parts/core.py`, `tests/test_loop_step.py`):
  - сохранить soft-continue поведение при fallback `scope_key` mismatch в implement переходе;
  - фиксировать `scope_key_mismatch_warn`, `expected_scope_key`, `selected_scope_key` как обязательную telemetry поверхность.
  - Findings (2026-03-03): на `TST-001` mismatch больше не является terminal blocker; flow продолжает выполнение и упирается в downstream причину (`review_pack_missing`), что подтверждает корректность soft-mode только для mismatch gate.
    Evidence: `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/aidd/reports/loops/TST-001/cli.loop-step.20260303-080315.log`.
  **AC:** loop не падает terminal на mismatch и продолжает итерацию, а mismatch детерминированно виден в payload/логах.

- [ ] **W102-6** Re-introduce strict scope mismatch transition gate after canonical scope emit hardening (`skills/aidd-loop/runtime/loop_step_parts/core.py`, `skills/aidd-loop/runtime/loop_step_stage_chain.py`, `tests/test_loop_step.py`, `tests/repo_tools/e2e_prompt/profile_full.md`):
  - после стабилизации stage_result emission вернуть fail-fast блокировку `scope_mismatch_transition_blocked` за feature-flag/policy toggle;
  - покрыть rollout тестами и e2e профилями (strict vs temporary soft mode).
  - Findings (2026-03-03): synthetic probe с `blocking_findings` на review показывает нормализацию blocked→continue и downstream terminal по `review_pack_missing`; перед возвратом strict mismatch gate нужно зафиксировать границы нормализации warn-reasons.
    Evidence: `.aidd_audit/loop_policy/20260303T080709Z/findings_summary_20260303.md`.
  **AC:** strict profile снова блокирует non-authoritative fallback scope, rollout контролируется конфигом и подтверждён тестами.

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

- [ ] **W101-15 (P1) Update full flow prompt script for Memory v2 (`aidd_test_flow_prompt_ralph_script_full.txt`)** `aidd_test_flow_prompt_ralph_script_full.txt`, `tests/repo_tools/smoke-workflow.sh`:
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

_Статус: план. Цель — ослабить E2E readiness gate только для scoped research WARN, не снижая fail-fast по ENV/contract mismatch._

### EPIC W2 — Scoped WARN policy in prompt contract

- [ ] **W102-1 (P0) Scoped research WARN for readiness gate (`R18/R12`)** `tests/repo_tools/e2e_prompt/profile_full.md`, `tests/repo_tools/e2e_prompt/profile_smoke.md`, `tests/repo_tools/test_e2e_prompt_contract.py`, `aidd_test_flow_prompt_ralph_script_full.txt`, `aidd_test_flow_prompt_ralph_script.txt`:
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

- [ ] **W105-2 (P0) Loop iteration timeout 1h contract** `skills/aidd-loop/runtime/loop_run_parts/core.py`, `tests/repo_tools/e2e_prompt/profile_full.md`, `aidd_test_flow_prompt_ralph_script_full.txt`, `tests/repo_tools/test_e2e_prompt_contract.py`:
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

## Wave 106 — Canonical review artifact integrity + loop/qa convergence

- [ ] **W106-1 (P0) Prevent reviewer marker update from deleting canonical review report** `skills/review/runtime/reviewer_tests.py`, `skills/aidd-core/runtime/runtime.py`, `tests/test_reviewer_tests.py`:
  - убрать удаление fallback `<scope>.json` при обновлении `.tests.json`;
  - разрешать legacy migration только для marker-payload, не для review-report payload.
  **AC:** после `reviewer_tests --status required` файл `aidd/reports/reviewer/<ticket>/<scope_key>.json` сохраняется.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_reviewer_tests.py`.
  **Effort:** S
  **Risk:** High

- [ ] **W106-2 (P0) Enforce canonical review report emission in review stage-chain** `skills/review/runtime/review_run.py`, `skills/review/runtime/review_report.py`, `skills/aidd-loop/runtime/loop_step_stage_chain.py`, `tests/test_review_run.py`, `tests/test_loop_step.py`:
  - зафиксировать canonical output path `aidd/reports/reviewer/<ticket>/<scope_key>.json` как единственный primary report;
  - исключить зависимость от non-canonical `.../I1/review-I1.json`.
  **AC:** stage_result evidence links всегда указывают на существующий canonical report; `review_report_missing` не воспроизводится после успешного review.
  **Deps:** W106-1
  **Regression/tests:** `python3 -m pytest -q tests/test_review_run.py tests/test_loop_step.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W106-3 (P0) Prompt-flow drift tripwire for review stage orchestration** `skills/review/SKILL.md`, `agents/reviewer.md`, `tests/test_review_agent.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - запретить manual `Write/cp` recovery path как primary;
  - запретить non-canonical runtime args (`--evidence`, `PASS_WITH_BLOCKERS`, `work_item_key=TST-001/I1`) в primary path.
  **AC:** primary orchestration не предлагает manual/non-canonical recovery; нарушения ловятся prompt-contract тестами.
  **Deps:** W106-2
  **Regression/tests:** `python3 -m pytest -q tests/test_review_agent.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W106-4 (P1) review-spec narrative/report payload alignment hardening** `skills/review-spec/SKILL.md`, `skills/aidd-core/runtime/prd_review.py`, `tests/test_prd_review.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - строить top-level narrative строго из structured report payload;
  - детерминированно выставлять mismatch marker только при реальном рассинхроне.
  **AC:** `narrative_vs_structured_mismatch` не возникает в READY-path без реального mismatch; при forced mismatch эмитится детерминированный WARN marker.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_prd_review.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W106-5 (P1) Emit minimal QA report for upstream-blocked path** `skills/qa/runtime/qa_parts/core.py`, `skills/qa/runtime/qa.py`, `tests/test_qa_agent.py`, `tests/test_qa_exit_code.py`:
  - при `qa:upstream_blocked` всегда эмитить минимальные QA artifacts (`.json` и `.pack.json`) с reason/evidence.
  **AC:** при blocked upstream создаются `aidd/reports/qa/<ticket>.json` и `aidd/reports/qa/<ticket>.pack.json`.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_qa_agent.py tests/test_qa_exit_code.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W106-6 (P2) Spec status consistency when tasklist is READY** `skills/tasks-new/runtime/tasks_new.py`, `skills/review-spec/*`, `tests/test_tasks_new.py`:
  - синхронизировать `spec`-статус с READY-path;
  - если `spec` не готов, писать явную deferred reason в structured payload.
  **AC:** `spec_status=draft` не остается в READY-path без явной причины в structured payload.
  **Deps:** W106-4
  **Regression/tests:** `python3 -m pytest -q tests/test_tasks_new.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W106-7 (P2) Audit summary reason_code extraction parity** `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/test_aidd_audit_runner.py`:
  - добавить поднятие `reason_code` из top-level loop result при неполном summary parser output.
  **AC:** summary-файлы отражают top-level `reason_code` (например, `actions_missing`).
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_aidd_audit_runner.py`.
  **Effort:** S
  **Risk:** Low
