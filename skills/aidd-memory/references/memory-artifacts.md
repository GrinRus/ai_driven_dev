# Memory Artifacts (Wave 101)

## Canonical paths
- `aidd/reports/memory/<ticket>.semantic.pack.json`
- `aidd/reports/memory/<ticket>.decisions.jsonl`
- `aidd/reports/memory/<ticket>.decisions.pack.json`

## Runtime entrypoints
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/memory_extract.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/decision_append.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/memory_pack.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/memory_slice.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/memory_verify.py`

## Notes
- Wave 101 PR-01 introduces command surfaces and bootstrap contracts.
- Runtime behavior is completed in later Wave 101 tasks (`W101-2..W101-5`).

