#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATUS=0

err() {
  printf '[error] %s\n' "$*" >&2
  STATUS=1
}

check_present() {
  local pattern="$1"; shift
  local scope=("$@");
  if ! rg -q "$pattern" "${scope[@]}"; then
    err "missing pattern: ${pattern} (scope: ${scope[*]})"
  fi
}

check_absent() {
  local pattern="$1"; shift
  local scope=("$@");
  if rg -n "$pattern" "${scope[@]}"; then
    err "forbidden pattern found: ${pattern}"
  fi
}

check_absent "Graph Read Policy" "${ROOT_DIR}/agents" "${ROOT_DIR}/skills" \
  "${ROOT_DIR}/skills/aidd-core/templates/workspace-agents.md"

check_present "Evidence read policy" "${ROOT_DIR}/skills/aidd-core/templates/workspace-agents.md"
check_present "AIDD:READ_LOG" "${ROOT_DIR}/skills/aidd-core/templates/workspace-agents.md"
check_present "rlm-slice.sh" "${ROOT_DIR}/skills/aidd-core/templates/workspace-agents.md"

exit $STATUS
