---
name: aidd-observability
description: Shared observability/runtime reporting ownership for diagnostics, inventory, identifiers, logs, and DAG export.
lang: en
model: inherit
user-invocable: false
---

## Scope
- This skill owns shared observability/reporting runtime entrypoints.
- Commands here support diagnostics, inventory generation, execution logs, and graph/report exports.
- Stage orchestration ownership remains in stage skills, `feature-dev-aidd:aidd-flow-state`, and `feature-dev-aidd:aidd-loop`.

## Canonical shared Python entrypoints
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-observability/runtime/doctor.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-observability/runtime/tools_inventory.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-observability/runtime/tests_log.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-observability/runtime/dag_export.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-observability/runtime/identifiers.py`

## Ownership guard
- Observability/reporting command modules must live under `skills/aidd-observability/runtime/*`.
- Consumers should reference `skills/aidd-observability/runtime/*` as canonical command paths.

## Additional resources
- [references/inventory-contract.md](references/inventory-contract.md) (when: ownership/inventory output is in question; why: keep report schema and consumers aligned).
- [references/diagnostics.md](references/diagnostics.md) (when: environment/diagnostics behavior is unclear; why: keep doctor/tests-log output deterministic).
