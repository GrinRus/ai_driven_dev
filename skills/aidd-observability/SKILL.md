---
name: aidd-observability
description: Owns shared observability/runtime reporting for diagnostics, inventory, identifiers, logs, DAG export, and artifact audit. Use when deterministic diagnostics, inventory exports, or machine-readable artifact consistency checks are required. Do not use when request scope is `status` stage summaries or `aidd-core` runtime ownership mapping.
lang: en
model: inherit
user-invocable: false
---

## Scope
- This skill owns shared observability/reporting runtime entrypoints.
- Commands here support diagnostics, inventory generation, execution logs, graph/report exports, and artifact truth auditing.
- Stage orchestration ownership remains in stage skills, `feature-dev-aidd:aidd-flow-state`, and `feature-dev-aidd:aidd-loop`.

## Canonical shared Python entrypoints
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-observability/runtime/artifact_audit.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-observability/runtime/doctor.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-observability/runtime/tools_inventory.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-observability/runtime/tests_log.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-observability/runtime/dag_export.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-observability/runtime/identifiers.py`

## Command contracts
### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-observability/runtime/artifact_audit.py`
- When to run: when AIDD artifact truth, status drift, missing expected reports, or template leakage must be checked in a machine-readable way.
- Inputs: workspace root or direct `aidd` root plus the feature ticket; optional explicit actual report paths.
- Outputs: deterministic JSON summary with artifact gate, truth checks, missing reports, leakage/drift buckets, and recommended next actions.
- Failure mode: non-zero exit on invalid root/ticket handling or serialization/import failures.
- Next action: fix the reported artifact inconsistencies or environment issue, then rerun the audit before trusting downstream readiness.

### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-observability/runtime/doctor.py`
- When to run: when environment/runtime path drift or tooling prerequisites are suspected.
- Inputs: optional workspace and diagnostics flags.
- Outputs: deterministic environment health report and actionable remediation hints.
- Failure mode: non-zero exit if required dependencies/path assumptions fail validation.
- Next action: apply reported environment fixes and rerun doctor before stage retry.

### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-observability/runtime/tools_inventory.py`
- When to run: when ownership/runtime API inventory must be regenerated for audits.
- Inputs: plugin root with optional output path filters.
- Outputs: normalized inventory snapshot for skills/runtime ownership checks.
- Failure mode: non-zero exit on inventory generation or schema serialization failures.
- Next action: fix inventory generation issue and rerun the command.

## Ownership guard
- Observability/reporting command modules must live under `skills/aidd-observability/runtime/*`.
- Consumers should reference `skills/aidd-observability/runtime/*` as canonical command paths.

## Additional resources
- [references/inventory-contract.md](references/inventory-contract.md) (when: ownership/inventory output is in question; why: keep report schema and consumers aligned).
- [references/diagnostics.md](references/diagnostics.md) (when: environment/diagnostics behavior is unclear; why: keep doctor/tests-log output deterministic and aligned with artifact audits).
