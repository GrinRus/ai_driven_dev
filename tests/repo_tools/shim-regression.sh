#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATUS=0

err() {
  printf '[error] %s\n' "$*" >&2
  STATUS=1
}

check_shim() {
  local tool="$1"
  local shim_path="${ROOT_DIR}/tools/${tool}"
  local target="${ROOT_DIR}/skills/review/scripts/${tool}"

  if [[ ! -f "$shim_path" ]]; then
    err "missing shim: tools/${tool}"
    return
  fi
  if ! rg -q "DEPRECATED" "$shim_path"; then
    err "shim lacks deprecation notice: tools/${tool}"
  fi
  if ! rg -q "exec .*skills/review/scripts/${tool}" "$shim_path"; then
    err "shim does not exec skills/review/scripts/${tool}"
  fi
  if [[ ! -x "$target" ]]; then
    err "skill script not executable: skills/review/scripts/${tool}"
  fi
}

check_shim "review-report.sh"
check_shim "review-pack.sh"
check_shim "reviewer-tests.sh"
check_shim "context-pack.sh"

if rg -n "\$\{CLAUDE_PLUGIN_ROOT\}/skills" "${ROOT_DIR}/hooks" >/dev/null; then
  err "hooks reference skills/** directly"
fi
if rg -n "\$\{CLAUDE_PLUGIN_ROOT\}/skills" "${ROOT_DIR}/tests" >/dev/null; then
  err "tests reference skills/** directly"
fi

exit "$STATUS"
