# Report Contract

## Run directory
- Every audit writes one directory:
  `aidd/reports/events/codex-e2e-audit/run-<timestamp>/`

## Required files
- `manifest.json`
- `rollup.json`
- `artifact_audit.json`
- `summary.json`
- `summary.md`

## `summary.json`
- Required top-level fields:
  - `run_id`
  - `profile`
  - `quality_profile`
  - `status`
  - `rollup_outcome`
  - `stage_classifications`
  - `primary_root_causes`
  - `artifact_quality_gate`
  - `top_findings`
  - `next_actions`
- Keep it machine-readable and deterministic.
- `top_findings` should focus on warn/error triage, not benign telemetry.

## `summary.md`
- Required sections:
  - `Run/log verdict`
  - `Warn/Error triage`
  - `Artifact quality verdict`
  - `Next actions`

## Raw artifacts
- Raw stage files stay in the locations already written by the launcher and rollup tools.
- The summary pack points to them; it does not replace them.
