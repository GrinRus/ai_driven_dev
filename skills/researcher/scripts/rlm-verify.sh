#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -z "${CLAUDE_PLUGIN_ROOT:-}" ]]; then
  export CLAUDE_PLUGIN_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
fi
export PYTHONPATH="${CLAUDE_PLUGIN_ROOT}:${PYTHONPATH:-}"

exec python3 "${CLAUDE_PLUGIN_ROOT}/tools/rlm_verify.py" "$@"
