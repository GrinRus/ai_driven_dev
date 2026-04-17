# Classification Matrix

## Source
- `tests/repo_tools/aidd_audit_runner.py rollup`
- `summary.json -> stage_classifications`
- `summary.json -> primary_root_causes`

## How to read stage outcomes
- Treat `effective_classification` as the user-facing verdict for the step.
- Treat `primary_root_cause` as the first remediation handle.
- Treat `rollup_outcome` as the run-level execution state, not the artifact quality state.

## Triage buckets
- `ENV_BLOCKER` or `ENV_MISCONFIG`
  - Meaning: host, cwd, plugin wiring, or disk preflight failure.
  - Typical root causes: `cwd_wrong`, `plugin_not_loaded`, low disk.
  - Response: stop and fix environment before retry.
- `PROMPT_EXEC_ISSUE`
  - Meaning: the stage launched but the prompt flow did not produce a trustworthy terminal outcome.
  - Typical root causes: `silent_stall`, `readiness_gate_failed`.
  - Response: inspect the specific step pack and readiness evidence.
- `FLOW_BUG`
  - Meaning: the runtime flow or wrapper contract behaved incorrectly.
  - Response: inspect launcher/summary/termination artifacts before rerun.
- `CONTRACT_MISMATCH`
  - Meaning: the stage output shape drifted from the expected contract.
  - Response: compare current runtime output with golden fixtures and report schema.
- `TELEMETRY_ONLY`
  - Meaning: informational or warning-only signal. Not every `TELEMETRY_ONLY` item belongs in top findings.
  - Response: include only actionable `WARN(...)` variants in warn/error triage.

## Latest-wins rule
- Prefer the rollup result for the latest run directory over earlier ad-hoc logs.
- Use raw stage captures only to explain a rollup classification, not to override it silently.
