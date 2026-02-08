#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -z "${CLAUDE_PLUGIN_ROOT:-}" ]]; then
  PLUGIN_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
  export CLAUDE_PLUGIN_ROOT="${PLUGIN_ROOT}"
fi
# shellcheck source=/dev/null
source "${CLAUDE_PLUGIN_ROOT}/skills/aidd-reference/wrapper_lib.sh"

# Contract note: aidd_run_python_module uses aidd_log_path + aidd_run_guarded internally.
aidd_run_python_module "core" "set-active-stage" "tools/set_active_stage.py" "$@"
