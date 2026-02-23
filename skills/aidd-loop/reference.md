# AIDD Loop Reference

This file contains stage-chain runtime references for loop-mode shared entrypoints.
Load it when you need exact command paths or transition details.

## Canonical stage-chain runtime
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_pack.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/preflight_result_validate.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/output_contract.py`
- Preflight prepare runtime is stage-chain-internal (not a direct operator command).

## Usage notes
- Prefer canonical paths in skills, agents, hooks, and docs.
- Do not reference `tools/*.sh` runtime entrypoints.
