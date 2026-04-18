# Product Backlog

> INTERNAL/DEV-ONLY: active engineering queue only.

Owner: feature-dev-aidd
Last reviewed: 2026-04-18
Status: active

Active backlog keeps only open work, current queue, and owner-review candidates.
Historical closure notes moved under `docs/archive/**`.

## Current Queue
- Gate A: `W145-2` -> `W145-3`
- Gate B: `W144-1` -> `W144-2`, then `W142-1` -> `W142-2`
- Gate C: `W146-2`
- Deferred after stabilization: `W147-*`

## Active Waves

## Wave 145 — TST-001 Run Findings Intake

- [ ] **W145-2 (P0) Classification precedence: non-zero exit + top-level error must override telemetry-only** `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/aidd_stage_launcher.py`, `tests/repo_tools/test_aidd_audit_runner.py`, `tests/repo_tools/test_aidd_stage_launcher.py`, `tests/fixtures/audit_tst001/*`
  **AC:** `exit_code!=0` + top-level error/result always beats telemetry-only classification.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_aidd_audit_runner.py tests/repo_tools/test_aidd_stage_launcher.py`

- [ ] **W145-3 (P1) `loop_runner_env_missing` detector hardening (init-only evidence)** `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/e2e_prompt/profile_full.md`, `tests/repo_tools/test_aidd_audit_runner.py`, `tests/repo_tools/test_e2e_prompt_contract.py`
  **AC:** valid non-interactive runner mode no longer produces false-positive `loop_runner_env_missing`.
  **Deps:** `W145-2`
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_aidd_audit_runner.py tests/repo_tools/test_e2e_prompt_contract.py`

## Wave 144 — Cleanup Signal Quality

- [ ] **W144-1 (P1) Reduce false-positive `safe-to-delete` in topology audit** `tests/repo_tools/repo_topology_audit.py`, `tests/test_repo_topology_audit.py`, `tests/repo_tools/build_e2e_prompts.py`, `tests/repo_tools/test_e2e_prompt_contract.py`
  **AC:** generated prompt artifacts with indirect usage are no longer marked `safe-to-delete`.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_repo_topology_audit.py tests/repo_tools/test_e2e_prompt_contract.py`

- [ ] **W144-2 (P2) Cleanup governance sync for generated report policy** `docs/release-docs-manifest.yaml`, `tests/repo_tools/repo_topology_audit.py`, `tests/test_repo_topology_audit.py`
  **AC:** generated revision guidance does not conflict with current cleanup governance.
  **Deps:** `W144-1`
  **Regression/tests:** `python3 -m pytest -q tests/test_repo_topology_audit.py`

## Wave 142 — Seed Convergence Rework

- [ ] **W142-1 (P0) Non-invasive seed guard layer + compatibility mode** `skills/aidd-loop/runtime/preflight_prepare.py`, `skills/aidd-core/runtime/stage_actions_run.py`, `tests/test_preflight_prepare.py`, `tests/test_stage_actions_run.py`
  **AC:** seed guard can be toggled without changing default behavior.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_preflight_prepare.py tests/test_stage_actions_run.py`

- [ ] **W142-2 (P1) Replay fixtures before merge** `tests/fixtures/audit_tst001/*`, `tests/repo_tools/test_aidd_audit_runner.py`
  **AC:** compatibility-mode replay matrix is locked before merge.
  **Deps:** `W142-1`
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_aidd_audit_runner.py`

## Wave 146 — Host-Agnostic E2E Prompt Rework

- [ ] **W146-2 (P0) Split host-neutral policy from host adapter overlays** `tests/repo_tools/e2e_prompt/*.md`, `tests/repo_tools/build_e2e_prompts.py`, `tests/repo_tools/test_e2e_prompt_contract.py`
  **AC:** host-specific overlays no longer duplicate policy core.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py tests/repo_tools/test_e2e_quality_prompt_contract.py`


## Deferred / Owner review

- `W147-*`: host-agnostic flow refactor remains deferred until current cleanup and prompt hardening settle.
- `docs/archive/rfc/host-agnostic-flow.md`: archived draft; reopen only with owner confirmation.
- `docs/archive/rfc/memory-v2.md`: archived draft; reopen only with owner confirmation.
- Compatibility removal candidates requiring explicit owner decision:
  - `aidd_runtime/**`
  - `legacy|compat|fallback|shadow` runtime and hook branches
  - archived experimental repo tools
