# AIDD Loop Reference

This file contains runtime-wrapper references for loop-mode shared entrypoints.
Load it when you need exact command paths or migration compatibility details.

## Canonical shared wrappers
- `${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/scripts/loop-pack.sh`
- `${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/scripts/preflight-prepare.sh`
- `${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/scripts/preflight-result-validate.sh`
- `${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/scripts/output-contract.sh`

## Compatibility shims
Legacy `tools/*.sh` paths remain available during migration and emit `DEPRECATED` to stderr before `exec` to canonical paths:
- `${CLAUDE_PLUGIN_ROOT}/tools/loop-pack.sh`
- `${CLAUDE_PLUGIN_ROOT}/tools/preflight-prepare.sh`
- `${CLAUDE_PLUGIN_ROOT}/tools/preflight-result-validate.sh`
- `${CLAUDE_PLUGIN_ROOT}/tools/output-contract.sh`

## Usage notes
- Prefer canonical paths in skills, agents, hooks, and docs.
- Keep `tools/*` references only when documenting shim compatibility.
- Shim behavior preserves arguments and exit codes via `exec`.
