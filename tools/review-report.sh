#!/usr/bin/env bash
set -euo pipefail

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-}"
if [[ -z "$PLUGIN_ROOT" ]]; then
  PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  export CLAUDE_PLUGIN_ROOT="$PLUGIN_ROOT"
fi

printf '[aidd] DEPRECATED: use %s\n' "${CLAUDE_PLUGIN_ROOT}/skills/review/scripts/review-report.sh" >&2
exec "${CLAUDE_PLUGIN_ROOT}/skills/review/scripts/review-report.sh" "$@"
