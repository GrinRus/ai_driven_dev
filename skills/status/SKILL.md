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
model: inherit
disable-model-invocation: true
user-invocable: true
---

Follow `feature-dev-aidd:aidd-core` and `feature-dev-aidd:aidd-loop`.

## Steps
1. Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/status/runtime/status.py --ticket <ticket>` as the sole canonical status entrypoint for this slash command.
2. `status.py` is read-only by default, and `/feature-dev-aidd:status` must be treated as a single-shot read-only report command. It must never bootstrap the workspace, invoke `/feature-dev-aidd:aidd-init`, call `init.py`, call `index_sync.py`, or rerun `status.py --refresh` unless the user explicitly requested a write/refresh path.
3. If `status.py` returns a read-only diagnostic such as missing workflow root or missing index snapshot, return that diagnostic and stop. The `Next action` field is advisory for the operator or a future explicit command, not permission to perform self-repair inside the same `/feature-dev-aidd:status` invocation.
4. Return only the runtime-produced status summary or read-only diagnostic, including active-ticket fallback behavior and derived `AIDD:ACTIONS_LOG`.

## Command contracts
### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/status/runtime/status.py`
- When to run: canonical status command for read-only ticket summary.
- Inputs: optional `--ticket <ticket>` (falls back to active ticket when available).
- Outputs: consolidated stage/status snapshot and artifact pointers, or a read-only diagnostic when the workspace/index is missing.
- Failure mode: non-zero exit when ticket resolution or workflow root lookup fails.
- Next action: run `/feature-dev-aidd:aidd-init` for missing workspace scaffolding, or rerun `status.py --refresh` when an explicit index rebuild is needed.

## Notes
- Loop stage: set `AIDD:ACTIONS_LOG` to the most recent `*.actions.json` under `aidd/reports/actions/<ticket>/...` (use `rg` if needed).
- Explicit write paths such as `status.py --refresh` or `python3 ${CLAUDE_PLUGIN_ROOT}/skills/status/runtime/index_sync.py --ticket <ticket>` are outside this slash command's default contract and must be triggered only by an explicit operator request.

## Additional resources
- Runtime implementation: [runtime/status.py](runtime/status.py) (when: status aggregation behavior needs debugging; why: verify ticket resolution and output fields).
