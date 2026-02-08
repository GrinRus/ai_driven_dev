#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${CLAUDE_PLUGIN_ROOT:-}" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  PLUGIN_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
  export CLAUDE_PLUGIN_ROOT="${PLUGIN_ROOT}"
fi

printf '[aidd] DEPRECATED: use %s\n' "${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/stage-result.sh" >&2
exec "${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/stage-result.sh" "$@"
