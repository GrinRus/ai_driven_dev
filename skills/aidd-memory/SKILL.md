---
name: aidd-memory
description: Owns shared Memory v2 runtime entrypoints (extract, append, pack, slice, verify) for deterministic context artifacts.
lang: en
allowed-tools:
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/memory_extract.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/decision_append.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/memory_pack.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/memory_slice.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/memory_verify.py *)"
model: inherit
user-invocable: false
---

## Scope
- This skill owns shared Memory v2 runtime entrypoints.
- Stage and shared skills consume these APIs to keep memory artifacts deterministic and pack-first.
- Memory artifacts are external context inputs, not chat transcript state.

## Canonical shared Python entrypoints
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/memory_extract.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/decision_append.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/memory_pack.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/memory_slice.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/memory_verify.py`

## Command contracts
### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/memory_extract.py`
- When to run: after research readiness when semantic memory must be materialized from docs/context packs.
- Inputs: `--ticket <ticket>` and optional source selectors.
- Outputs: semantic memory pack artifact path/status payload.
- Failure mode: non-zero exit when extraction inputs are missing or extraction budget cannot be enforced.
- Next action: fix source inputs/budget config and rerun extraction.

### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/memory_pack.py`
- When to run: when decision log and semantic memory must be assembled into deterministic memory packs.
- Inputs: `--ticket <ticket>` and optional pack budget overrides.
- Outputs: memory pack assembly status and written artifact refs.
- Failure mode: non-zero exit on invalid upstream artifacts or serialization contract drift.
- Next action: run verification, repair invalid artifacts, then rerun pack assembly.

## Ownership guard
- Memory runtime modules must be implemented under `skills/aidd-memory/runtime/*`.
- Consumers should reference these canonical runtime paths instead of duplicating memory logic.

## Additional resources
- [references/memory-artifacts.md](references/memory-artifacts.md) (when: artifact names or lifecycle is unclear; why: keep memory paths and write/read order consistent across stages).

