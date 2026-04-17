---
name: aidd-e2e-quality-audit
description: Use only when explicitly invoked as $aidd-e2e-quality-audit to run or review an AIDD live/e2e quality audit for this repository. This skill is limited to AIDD run audit, warn/error/root-cause triage, and AIDD artifact quality review; do not use it for normal repo development, do not use it as a stage skill for target projects, and do not trigger it implicitly.
---

# AIDD E2E Quality Audit

## Scope
- This is a repo-local Codex skill for auditing the AIDD project itself.
- It is audit-only for `v1`: no backlog writes, no auto-remediation, no scheduled automations, no broad repo editing.
- Existing AIDD runtime in `skills/**`, `tests/repo_tools/**`, `docs/e2e/*.txt`, and TST-002 prompt fragments remain the source of truth. This skill orchestrates them; it does not reimplement them.

## Default command
- Run the repo orchestrator:
  `python3 tests/repo_tools/aidd_e2e_live_audit.py --project-dir <workspace-root> --plugin-dir <repo-root> --ticket <ticket> --profile <smoke|full> --quality-profile <smoke|full>`
- The orchestrator already performs:
  - prompt fixture sanity via `tests/repo_tools/build_e2e_prompts.py --check`
  - single-threaded live stage execution via `tests/repo_tools/aidd_stage_launcher.py`
  - rollup classification via `tests/repo_tools/aidd_audit_runner.py rollup`
  - machine-readable artifact review via `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-observability/runtime/artifact_audit.py`

## Operating rules
1. Stay in audit mode. Do not drift into feature work or broad cleanup.
2. Keep stage execution single-threaded and deterministic. Do not parallelize launcher runs.
3. Use the summary pack under `aidd/reports/events/codex-e2e-audit/run-*/` as the first read target.
4. Report findings and next actions only. Do not auto-fix unless the user separately asks for remediation.
5. Do not spawn subagents unless the user explicitly asks for parallel analysis or subagents.
6. If the user explicitly asks for parallel analysis, fan out only post-run read-only analysis to `.codex/agents/aidd_log_triager.md` and `.codex/agents/aidd_artifact_reviewer.md`.

## Expected output
- Always separate:
  - run/log verdict
  - warn/error triage
  - artifact quality verdict
  - next actions
- Prefer `summary.json` and `summary.md` from the orchestrator run directory over ad-hoc narration.
- When the audit is blocked, surface the fail-fast reason from the run pack and stop there.

## Additional resources
- [references/flow-runbook.md](references/flow-runbook.md) (when: you need the launcher order, preflight behavior, or run directory layout; why: keeps the live audit flow aligned with the repo orchestrator contract).
- [references/classification-matrix.md](references/classification-matrix.md) (when: rollup warnings/errors need normalization into root causes and verdicts; why: maps `aidd_audit_runner` output into stable triage buckets).
- [references/artifact-quality-rubric.md](references/artifact-quality-rubric.md) (when: `aidd/docs/**` or `aidd/reports/**` quality is in doubt; why: defines what counts as leakage, missing reports, status drift, or readiness mismatch).
- [references/report-contract.md](references/report-contract.md) (when: you need to validate `summary.json` or `summary.md`; why: keeps the final pack deterministic and reviewable).
