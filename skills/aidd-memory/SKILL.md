---
name: aidd-memory
description: Owns shared memory v2 artifacts for semantic extraction and decision logs. Use when stage/runtime needs canonical memory read or write operations. Do not use when request belongs to stage-local implementation work without shared memory artifact changes.
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
- This skill is shared and preload-only.
- Use it for deterministic memory artifact generation, validation, and retrieval.
- Memory artifacts live under `aidd/reports/memory/`.

## Canonical command paths
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/memory_extract.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/decision_append.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/memory_pack.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/memory_slice.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/memory_verify.py`

## Command contracts
### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/memory_extract.py`
- When to run: after research artifacts are ready and semantic memory must be refreshed.
- Inputs: `--ticket <ticket>` and optional budget overrides.
- Outputs: `aidd/reports/memory/<ticket>.semantic.pack.json`.
- Failure mode: non-zero exit when source artifacts are missing or payload fails schema/budget validation.
- Next action: fix missing/invalid source artifacts and rerun extract.

### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/decision_append.py`
- When to run: loop/runtime must persist a new decision in append-only form.
- Inputs: `--ticket`, `--title`, `--decision` plus optional rationale/tags/supersedes.
- Outputs: append line in `aidd/reports/memory/<ticket>.decisions.jsonl`.
- Failure mode: non-zero exit when payload is invalid.
- Next action: correct payload fields and retry append.

### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/memory_pack.py`
- When to run: after one or more decision appends to rebuild decisions pack.
- Inputs: `--ticket` and optional `--top-n`.
- Outputs: `aidd/reports/memory/<ticket>.decisions.pack.json`.
- Failure mode: non-zero exit on malformed decision log entries.
- Next action: repair invalid decision entries and rebuild pack.

### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/memory_verify.py`
- When to run: validation gate for semantic/decision artifacts.
- Inputs: one or more artifact paths (`--semantic`, `--decision`, `--decisions-pack`).
- Outputs: validation status diagnostics.
- Failure mode: non-zero exit with field-level error messages.
- Next action: regenerate or manually fix artifact payload.

## Additional resources
- Runtime extractor: [runtime/memory_extract.py](runtime/memory_extract.py) — when: semantic extraction behavior or budgets are unclear; why: confirms deterministic extraction/trimming rules.
- Runtime pack builder: [runtime/memory_pack.py](runtime/memory_pack.py) — when: decision supersede/conflict behavior needs verification; why: defines canonical active/superseded pack assembly.
