---
name: status
description: Generates consolidated ticket status summary and key artifact pointers. Use when checking current stage state or handoff readiness. Do not use when the request is diagnostics/inventory from `aidd-observability` or flow-state mutation via `aidd-flow-state`.
argument-hint: [$1]
lang: en
prompt_version: 1.0.9
source_version: 1.0.9
allowed-tools:
  - Read
  - "Bash(rg *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/status/runtime/status.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/status/runtime/index_sync.py *)"
model: inherit
disable-model-invocation: false
user-invocable: true
---

Follow `feature-dev-aidd:aidd-core` and `feature-dev-aidd:aidd-loop`.

## Steps
1. Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/status/runtime/status.py --ticket <ticket>` as the sole canonical status entrypoint; it may refresh index data internally when needed.
2. Use `python3 ${CLAUDE_PLUGIN_ROOT}/skills/status/runtime/index_sync.py --ticket <ticket>` only as a manual repair or debugging path when `status.py` cannot recover the index on its own.
3. Return the read-only status summary sourced from `status.py`, including active-ticket fallback behavior and derived `AIDD:ACTIONS_LOG`.

## Command contracts
### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/status/runtime/status.py`
- When to run: canonical status command for read-only ticket summary.
- Inputs: optional `--ticket <ticket>` (falls back to active ticket when available).
- Outputs: consolidated stage/status snapshot and artifact pointers, with internal index refresh when the snapshot is missing.
- Failure mode: non-zero exit when ticket resolution or index/report reads fail.
- Next action: refresh index or fix missing ticket context, then rerun status runtime.

### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/status/runtime/index_sync.py`
- When to run: manual repair/debug path only when index data must be rebuilt outside the normal `status.py` flow.
- Inputs: `--ticket <ticket>` and current workspace index sources.
- Outputs: rebuilt index snapshot for the current ticket.
- Failure mode: non-zero exit when ticket resolution or index serialization fails.
- Next action: fix the index source problem, rerun the sync, then rerun `status.py`.

## Notes
- Loop stage: set `AIDD:ACTIONS_LOG` to the most recent `*.actions.json` under `aidd/reports/actions/<ticket>/...` (use `rg` if needed).

## Additional resources
- Runtime implementation: [runtime/status.py](runtime/status.py) (when: status aggregation behavior needs debugging; why: verify ticket resolution and output fields).
