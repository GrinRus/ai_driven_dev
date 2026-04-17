# Wave 120/121/136 Closure Runbook

> INTERNAL/DEV-ONLY: closure summary for stabilization waves `120`, `121`, `136`.

Owner: feature-dev-aidd
Last reviewed: 2026-04-18
Status: historical

_Local evidence note: references like `aidd/reports/**` point to workspace-local artifacts and are not part of this git repository._

## Closure Date
- 2026-04-09

## Completed Scope
- Wave 120: core runtime and stage-contract stabilization.
- Wave 121: prompt/audit/replay hygiene and deterministic classification surfaces.
- Wave 136: integration closure, regression matrix verification, release-gate sign-off.

## Execution Audit Against PR Plan
- `PR-00 (Preflight baseline)`: completed.
  - Evidence: `aidd/reports/events/w120-w121-w136-baseline-2026-04-09.md`.
  - Notes: baseline matrix `task -> test -> artifact` captured in report.
- `PR-01 (W120-1)`: completed by regression verification.
  - Command: `python3 -m pytest -q tests/test_loop_run.py tests/test_review_run.py tests/test_qa_agent.py tests/repo_tools/test_e2e_prompt_contract.py`.
  - Result: pass.
- `PR-02 (W120-2)`: completed by regression verification.
  - Command: `python3 -m pytest -q tests/test_stage_actions_run.py tests/test_gate_workflow_preflight_contract.py tests/test_wave93_validators.py tests/test_prompt_lint.py`.
  - Result: pass.
- `PR-03 (W120-3 + W120-4)`: completed by regression verification.
  - Command: `python3 -m pytest -q tests/test_loop_step.py tests/test_loop_run.py tests/repo_tools/test_e2e_prompt_contract.py`.
  - Result: pass.
- `PR-04 (W120-5)`: completed by regression verification.
  - Command: `python3 -m pytest -q tests/test_research_command.py tests/test_research_check.py tests/test_gate_workflow.py tests/test_research_rlm_e2e.py tests/test_loop_run.py`.
  - Result: pass.
- `PR-05 (W120-6)`: completed by regression verification.
  - Command: `python3 -m pytest -q tests/test_tasklist_check.py tests/test_tasks_new_runtime.py tests/test_qa_agent.py tests/test_qa_exit_code.py tests/repo_tools/test_e2e_prompt_contract.py`.
  - Result: pass.
- `PR-06 (W120-7)`: completed by regression verification.
  - Command: `python3 -m pytest -q tests/test_resources.py tests/test_context_gc.py tests/test_hook_rw_policy.py tests/repo_tools/test_e2e_prompt_contract.py` + `tests/repo_tools/smoke-workflow.sh`.
  - Result: pass.
- `PR-07 (W120-8)`: completed by regression verification.
  - Command: `python3 -m pytest -q tests/test_qa_agent.py tests/test_stage_result.py tests/test_loop_run.py tests/test_tasklist_check.py`.
  - Result: pass.
- `PR-08 (W121-1 + W121-2)`: completed by regression verification.
  - Command: `python3 -m pytest -q tests/test_prd_review_agent.py tests/test_prompt_lint.py tests/repo_tools/test_e2e_prompt_contract.py`.
  - Result: pass.
- `PR-09 (W121-3)`: completed by regression verification.
  - Command: `python3 -m pytest -q tests/repo_tools/test_aidd_stage_launcher.py tests/repo_tools/test_aidd_audit_runner.py tests/repo_tools/test_e2e_prompt_contract.py`.
  - Result: pass.
- `PR-10 (W121-4 + W121-5)`: completed by regression verification.
  - Command: `python3 -m pytest -q tests/repo_tools/test_aidd_audit_runner.py tests/test_tasks_new_runtime.py tests/test_tasklist_check.py tests/test_prd_ready_check.py tests/repo_tools/test_e2e_prompt_contract.py`.
  - Result: pass.
- `PR-11 (W121-6)`: completed by regression verification.
  - Command: `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py tests/repo_tools/test_e2e_quality_prompt_contract.py`.
  - Result: pass.
- `PR-12 (W136-1)`: completed by regression verification.
  - Command: `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py tests/repo_tools/test_e2e_quality_prompt_contract.py tests/repo_tools/test_aidd_audit_runner.py` + `tests/repo_tools/smoke-workflow.sh`.
  - Result: pass.
- `PR-13 (W136-2)`: completed by parity verification.
  - Verified refs: `.github/workflows/ci.yml`, `docs/release-docs-manifest.yaml`, `docs/runbooks/marketplace-release.md`.
  - Result: required checks and release sign-off criteria aligned.
- `PR-14 (W136-3)`: completed.
  - Updated: `CHANGELOG.md`, `README.md`, `README.en.md`, `AGENTS.md`, `docs/backlog.md`, `docs/runbooks/tst001-audit-hardening.md`.
  - Added closure runbook and linked evidence.

## Verification Gates
1. Full lint/test gate
- `tests/repo_tools/ci-lint.sh`
- Expected: pass (no hard failures).

1. Smoke workflow gate
- `tests/repo_tools/smoke-workflow.sh`
- Expected: pass with deterministic gate-workflow and loop smoke behavior.

1. Prompt/audit contract gate
- `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py tests/repo_tools/test_e2e_quality_prompt_contract.py tests/repo_tools/test_aidd_audit_runner.py`
- Expected: pass, deterministic reason-code and classification mapping.

1. Wave regression bundle
- `python3 -m pytest -q tests/test_stage_actions_run.py tests/test_gate_workflow_preflight_contract.py tests/test_wave93_validators.py tests/test_prompt_lint.py tests/test_loop_step.py tests/test_loop_run.py tests/test_research_command.py tests/test_research_check.py tests/test_gate_workflow.py tests/test_research_rlm_e2e.py tests/test_tasklist_check.py tests/test_tasks_new_runtime.py tests/test_qa_agent.py tests/test_qa_exit_code.py tests/test_resources.py tests/test_context_gc.py tests/test_hook_rw_policy.py tests/test_stage_result.py tests/test_prd_review_agent.py tests/test_prd_ready_check.py`
- Expected: pass.

## Evidence
- Baseline report: `aidd/reports/events/w120-w121-w136-baseline-2026-04-09.md`.
- TST-001 classification policy: `docs/runbooks/tst001-audit-hardening.md`.
- CI required checks policy: `docs/runbooks/marketplace-release.md`.

## Residual Risks
- Runtime module size warnings (`runtime-module-guard` warn threshold) remain technical debt; they are non-blocking for current closure.
- Advisory-only skill-eval path requires `ANTHROPIC_API_KEY`; not a blocker for required checks.

## Next Roadmap
- Historical next step at closure time: move backlog focus to Waves `122..125`.
- Current source of truth for active roadmap priority is `docs/backlog.md`.
