# AIDD Loop Reference

This file contains runtime-wrapper references for loop-mode shared entrypoints.
Load it when you need exact command paths or transition details.

## Canonical shared wrappers
- `${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/scripts/loop-pack.sh`
- `${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/scripts/preflight-prepare.sh`
- `${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/scripts/preflight-result-validate.sh`
- `${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/scripts/output-contract.sh`

## Usage notes
- Prefer canonical paths in skills, agents, hooks, and docs.
- Do not reference `tools/*.sh` runtime entrypoints.
