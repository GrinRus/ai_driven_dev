INTERNAL/DEV-ONLY
Owner: feature-dev-aidd
Last reviewed: 2026-04-17
Status: active

# TST-001 Phase 1 — Code-First Loop Audit (No Runtime Runs)

Date: 2026-04-16  
Scope: static audit of code + commit history only (`merge-base..HEAD`), no stage-flow execution used as evidence.

Branch: `codex/wave-149-tasks-new-stabilize`  
Merge-base: `9e66513736ba488715da940b756d3c397efd00ba`  
HEAD: `5a6e8fc226093c860ee10b7cfa8bebcd6eb1f5ae`

## Stage Loop Matrix

| Stage | Blocked/Pending Trigger (Code Source) | Retry Policy | Stop Condition | Terminal Reason Codes / Outcomes | Loop Risk |
| --- | --- | --- | --- | --- | --- |
| `idea` | PRD validator blocks on question numbering gaps, missing/extra `Q<N>` pairs, invalid compact answers, `Status != READY`, open questions, missing research link (`skills/aidd-core/runtime/analyst_guard.py:227-387`). | No implicit endless retry in runtime. External retry is Q/A closure cycle. In loop mode, question retry is auto-applied once (`skills/aidd-loop/runtime/loop_step_parts/core.py:1910-2073`). | `Status: READY` + strict Q/A bijection + no unresolved open questions. | `blocked` validator error; second blocked question cycle in loop emits `reason_code=prompt_flow_blocker`. | High |
| `research` | Hard block if `AIDD:RESEARCH_HINTS` lacks paths/keywords (`skills/researcher/runtime/research.py:536-540`). Pending reasons are emitted when RLM not ready (`skills/researcher/runtime/research.py:675-700`). | Bounded auto-recovery/finalize once (`skills/researcher/runtime/research.py:311-372`, `637-667`). Downstream checker does one finalize probe (`skills/plan-new/runtime/research_check.py:118-158`). | `rlm_status=ready` with mandatory RLM baseline artifacts validated (`skills/plan-new/runtime/research_check.py:45-69,166`). | `research_artifacts_missing`, `research_artifacts_invalid`, `rlm_status_pending_finalize_failed`, pending with deterministic `reason_code + next_action`. | Medium |
| `plan` | Stage contract blocks early unless `prd_check + research_check` pass (`skills/plan-new/SKILL.md:30-37`). | No unbounded retry in code. Research gate probe is bounded once via `research_check.py`. | Gate pass + planner/validator verdict no blockers. | Blocking inherited from `research_check` and `prd_check` failures (e.g. `rlm_status_pending`, artifact invalid/missing). | Medium |
| `review-spec` | Plan/PRD gates block on missing sections/status mismatch/open actions/critical findings (`skills/aidd-core/runtime/plan_review_gate.py:173-207`, `skills/aidd-core/runtime/prd_review_gate.py:301-399`). PRD report with `--require-ready` fails when not ready (`skills/aidd-core/runtime/prd_review.py:544-550`). | No iterative self-loop in runtime; rerun is explicit after upstream PRD/plan fixes (`skills/review-spec/SKILL.md:40-42`). | `recommended_status=ready` in PRD report and all gate checks pass. | `review_not_ready`, gate BLOCK outcomes (status mismatch, open action items, blocking findings). | Medium |
| `tasks` | Runtime blocks for missing project QA contract (`project_contract_missing`) and validator errors (`skills/tasks-new/runtime/tasks_new.py:288-339`). Category classification is in validator (`skills/aidd-flow-state/runtime/tasklist_validate.py:49-67,141-148,195-212`). | Explicit bounded retry guidance only for `repairable_structure` (`skills/tasks-new/SKILL.md:36-39`, `skills/tasks-new/runtime/tasks_new.py:326-334`). | `tasklist_check=ok` and postcondition artifact exists/non-empty (`skills/tasks-new/runtime/tasks_new.py:348-356`). | `project_contract_missing`, `cwd_wrong`, tasklist postcondition failures, categorized `upstream_blocker`. | High |
| `implement` | Shared stage runtime blocks on invalid actions contract and seed scope cascade (`skills/aidd-core/runtime/stage_actions_run.py:390-456`, `210-291`). | One canonicalization retry max for actions payload (`skills/aidd-core/runtime/stage_actions_run.py:421-433`). | Valid `aidd.actions.v1` payload accepted; no scope-cascade violation. | `contract_mismatch_actions_shape`, `seed_scope_cascade_detected`. | Medium |
| `review` | Same shared actions contract as implement + required canonical review report (`skills/review/runtime/review_run.py:52-61`; `stage_actions_run.py`). | One canonicalization retry max via shared runner. | Review report present and actions contract valid. | `review_report_missing`, `contract_mismatch_actions_shape`. | Medium |
| `qa` | QA runtime blocks on malformed `AIDD:TEST_EXECUTION`, missing project contract, cwd mismatch, missing preflight in loop mode, blocked report status, stage-result emit failure (`skills/qa/runtime/qa_parts/core.py:533-599,770-822`). | Fail-fast policy in skill (no guessed retries) (`skills/qa/SKILL.md:43-47`). | Tests/report meet policy, report not `BLOCKED`, stage-result emission succeeds. | `project_contract_missing`, `tests_cwd_mismatch`, `preflight_missing`, `qa_stage_result_emit_failed`. | High |
| `loop` | Blocked reason classification + policy matrix (`skills/aidd-loop/runtime/loop_block_policy.py:165-205`, `loop_run_parts/core.py:1776-1789`). Timeout outcomes distinguish active stream vs budget exhaustion (`loop_run_parts/core.py:891-911,1440-1514`). | Question retry in loop-step: exactly 1 (`loop_step_parts/core.py:1640-1643,1917,2055-2073`). Recoverable blocked retries in loop-run: bounded by budget (`loop_run_parts/core.py:451-458,2326-2370`). Fail-fast on repeated no-new-evidence (`loop_run_parts/core.py:2112-2157,2196-2275`). | `done/ship` or terminal blocked when reason is non-recoverable, budget exhausted, retry budget exhausted, or repeated-no-evidence fail-fast. | `prompt_flow_blocker`, `loop_runner_permissions`, `seed_stage_active_stream_timeout`, `seed_stage_budget_exhausted`, `repeated_command_failure_no_new_evidence`, `scope_drift_recoverable` (recoverable path). | High |

## Loop-Risk Points by Stage (Code-Level)

| Stage | Loop Risk Point | Code Anchor | Expected Hard Stop |
| --- | --- | --- | --- |
| `idea` | `AIDD:ANSWERS` parser scans full section; inline instructional examples can be parsed as real answers. | `skills/aidd-core/runtime/analyst_guard.py:148-161`, template examples at `skills/idea-new/templates/prd.template.md:25-26`. | Stop with missing/extra answer mismatch; do not auto-loop beyond one retry in loop mode. |
| `research` | Auto finalize probe can return `pending` repeatedly if upstream RLM remains unresolved. | `skills/researcher/runtime/research.py:311-372,637-700`. | One bounded auto finalize; then deterministic pending with `next_action`. |
| `plan` | Research gate softening is only for expected stage `plan`; wrong stage usage can hard-block repeatedly if caller retries blindly. | `skills/plan-new/runtime/research_check.py:34-42,138-151`. | Stop after probe outcome; do not convert non-plan pending to soft pass. |
| `review-spec` | Narrative vs structured findings mismatch can lead to repeated reruns if caller trusts narrative instead of report payload. | `skills/aidd-core/runtime/prd_review.py:361-365,423-435`; `skills/review-spec/SKILL.md:40-42`. | Use report payload as source of truth; rerun only after upstream artifact changes. |
| `tasks` | Category-driven remediation can loop if `upstream_blocker` is incorrectly treated as repairable. | `skills/tasks-new/runtime/tasks_new.py:321-335`; `skills/aidd-flow-state/runtime/tasklist_validate.py:49-67`. | `upstream_blocker` is terminal for stage attempt; bounded retry only for `repairable_structure`. |
| `implement` | Shared action payload recovery retries exactly once; repeated bad payloads must terminate. | `skills/aidd-core/runtime/stage_actions_run.py:421-446`. | Second invalid contract is terminal `contract_mismatch_actions_shape`. |
| `review` | Missing canonical review report can cause external rerun loops if not fixed upstream. | `skills/review/runtime/review_run.py:52-61`. | Immediate terminal blocker until report exists. |
| `qa` | Contract/test-cwd failures can be retried indefinitely by caller if reason precedence ignored. | `skills/qa/runtime/qa_parts/core.py:588-599,649-656`. | Treat `project_contract_missing/tests_cwd_mismatch` as primary blocker. |
| `loop` | Policy retries (`recoverable_retry`) + no-convergence branch can become long-running without bounded fail-fast controls. | `skills/aidd-loop/runtime/loop_run_parts/core.py:2326-2370,2196-2294,2112-2157`. | Retry budget + repeated-no-evidence fail-fast + stage budget exhaustion. |

## Commit Regression Matrix (`merge-base..HEAD`)

| Commit | Changed Loop/Retry Branches | Potential Regression / Loop Impact | Evidence |
| --- | --- | --- | --- |
| `fee7ac5` | Removed spec interview reason-codes from loop-step question retry set (`skills/aidd-loop/runtime/loop_step_parts/core.py`). Added category-based tasks remediation (`skills/tasks-new/runtime/tasks_new.py`, `skills/aidd-flow-state/runtime/tasklist_validate.py`). | Legacy reason-codes (`missing_spec_answers`, `spec_questions_unresolved`) are no longer auto-retry candidates; if emitted by stale callers, stage may stay blocked without retry. Tasks stage behavior now strongly depends on issue categorization (`upstream_blocker` vs `repairable_structure`) for bounded retry path. | `git show fee7ac5 -- skills/aidd-loop/runtime/loop_step_parts/core.py`; `git show fee7ac5 -- skills/tasks-new/runtime/tasks_new.py`; `git show fee7ac5 -- skills/aidd-flow-state/runtime/tasklist_validate.py`. |
| `99504ce` | Tightened analyst question parsing and dialog compatibility (`skills/aidd-core/runtime/analyst_guard.py`). | Reduced false negatives for `Question N`, but stricter dialog parsing can still block if template/examples leak into parsed answer set. | `git show 99504ce -- skills/aidd-core/runtime/analyst_guard.py`. |
| `5a6e8fc` | `idea-new` analyst-check now syncs index on both success and validation failure (`skills/idea-new/runtime/analyst_check.py`). | Improves question-closure telemetry consistency; does not itself add retry loops, but can alter orchestration behavior that depends on index freshness. | `git show 5a6e8fc -- skills/idea-new/runtime/analyst_check.py`. |

### Introducing Commit Map (Per Key Risk)

| Risk | Introducing Commit (blame) | Notes |
| --- | --- | --- |
| Strict compact answer parser in idea gate | `bc76775c` (`analyst_guard.py:41`) | Parser reads compact `Q=` patterns across the whole answers section. |
| Q/A bijection hard-stop (`missing_answers` / `extra_answers`) | `bc76775c` + legacy core (`analyst_guard.py:333-351`) | Core anti-loop stop condition for idea stage. |
| Inline compact examples in PRD template | `53145731` (`prd.template.md:25-26`) | Possible parser collision risk if not filtered in guard. |
| Inline compact example in plan template | `bc76775c` (`plan.template.md:20`) | Same parser-collision class in plan artifacts. |
| Loop question retry base reason set | `05471c0a` (`loop_step_parts/core.py:93-98`) | Baseline for auto question retry candidate detection. |
| Tasks category-based retry gating | `fee7ac5` (`tasks_new.py:321-330`, `tasklist_validate.py:49-58`) | Governs bounded retry vs upstream terminal stop. |
| Shared actions one-retry contract | `7a873127` + `53ef43a0` (`stage_actions_run.py:421-446`) | Exactly one canonicalization retry before terminal mismatch. |
| Loop repeated-no-evidence fail-fast | `afd20d88` (`loop_run_parts/core.py:2112-2157`) | Stops repeated blocked policy loops. |
| Loop timeout reason split (`active_stream` vs budget) | `05471c0a` (`loop_run_parts/core.py:891-911`) | Distinguishes no-convergence vs budget exhaustion behavior. |

## Test Gap Matrix (Static)

| Stage | Existing Coverage (Static) | Missing / Weak Coverage | Gap Risk |
| --- | --- | --- | --- |
| `idea` | Strong unit coverage for Q/A parity, compact format, open-questions sync (`tests/test_analyst_dialog.py`), plus sync-index behavior (`tests/test_idea_new_analyst_check.py`). | No direct test that `analyst_guard` ignores inline instructional compact examples inside `## AIDD:ANSWERS` (template-style examples). | High |
| `research` | `research_check` covers pending/ready/softening/finalize-fail branches (`tests/test_research_check.py`). | Limited direct tests for full `research.py` auto-finalize + pending handoff path integration (`pending_reason_code`, `next_action`) under repeated unresolved states. | Medium |
| `plan` | Research gate behavior tested via `research_check` and workflow tests. | No dedicated plan-stage integration test for full gate chain (`prd_check + research_check + validator`) with anti-loop stop semantics. | Medium |
| `review-spec` | Gate/report tests exist (`tests/test_plan_review_gate.py`, `tests/test_gate_prd_review.py`, `tests/test_prd_review_agent.py`, `tests/test_prd_review_cli.py`). | No direct test ensuring orchestration always trusts structured report over narrative mismatch for retry/stop decisions. | Medium |
| `tasks` | Strong runtime coverage for category outputs and bounded retry guidance (`tests/test_tasks_new_runtime.py`). | No execution-level test that orchestrator enforces exactly one retry attempt (current guard is guidance + category, not explicit runtime retry counter in `tasks_new.py`). | Medium |
| `implement` | Shared stage-run tests cover scope guard and contract diagnostics (`tests/test_stage_actions_run.py`). | No explicit test for second consecutive invalid actions payload in real stage wrapper path (ensure no extra retries beyond one canonicalization). | Medium |
| `review` | Coverage for missing review report (`tests/test_review_run.py`). | Thin coverage for review stage contract-mismatch propagation and retry suppression behavior. | Medium |
| `qa` | Coverage for contract-missing exit behavior and blocked report (`tests/test_qa_exit_code.py`, `tests/test_gate_qa.py`). | Limited tests for loop-mode `preflight_missing` stop and precedence when `tests_cwd_mismatch` co-occurs with missing top-level result telemetry. | Medium |
| `loop` | Strong coverage for ralph recoverable paths, prompt-flow blocker, timeouts, permissions, repeated-no-evidence (`tests/test_loop_step.py`, `tests/test_loop_run.py`). | No regression test asserting behavior for removed legacy spec reason-codes after `fee7ac5`; no dedicated test for “stale reason code from stage payload” fallback policy. | Medium |

## Gate to Phase 2 (Runtime/Logs) — Ready Scenarios

Expected stop-conditions are now defined for all stages above.  
Each listed risk has code anchors and commit attribution.

Proceed to runtime validation with these exact scenarios:

1. `idea`: PRD with template-style inline compact examples + real answers; verify no false `extra_answers`/`missing_answers` loop.
2. `idea`: force blocked question cycle and ensure loop-step applies only one compact-answer retry then `prompt_flow_blocker`.
3. `research`: unresolved RLM with `--auto`; verify single finalize probe and deterministic pending handoff (`reason_code + next_action`) without repeated internal loop.
4. `plan`: pending research in non-plan expected stage; verify no soft-pass drift and terminal stop behavior.
5. `review-spec`: narrative/report mismatch fixture; verify decision source is structured report and rerun only after upstream artifact change.
6. `tasks`: two fixtures: `upstream_blocker` and `repairable_structure`; verify only repairable path is retriable and limited to one retry.
7. `implement/review`: invalid actions payload twice; verify one canonicalization retry then terminal `contract_mismatch_actions_shape`.
8. `qa`: malformed test execution + `project_contract_missing` + `tests_cwd_mismatch` cases; verify primary reason precedence and no repeated guessed retries.
9. `loop`: `blocking_findings` under `BLOCKED_POLICY=ralph`; verify recoverable retry path and budget accounting.
10. `loop`: timeout with active stream (`seed_stage_active_stream_timeout`) vs budget exhaustion (`seed_stage_budget_exhausted`); verify non-terminal/no-convergence vs watchdog terminal split.
11. `loop`: repeated policy block without new evidence; verify fail-fast `repeated_command_failure_no_new_evidence`.
12. `loop`: legacy removed reason-code payload simulation (`spec_questions_unresolved`); verify current behavior and whether compatibility fallback is needed.
