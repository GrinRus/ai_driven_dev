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

check_shim_runtime_warning() {
  local tool="$1"
  local shim_path="${ROOT_DIR}/tools/${tool}"
  local output rc
  set +e
  output="$(CLAUDE_PLUGIN_ROOT="${ROOT_DIR}" "${shim_path}" --help 2>&1)"
  rc=$?
  set -e
  if [[ "$output" != *"DEPRECATED"* ]]; then
    err "shim did not emit deprecation warning at runtime: tools/${tool} (rc=${rc})"
  fi
}

check_smoke_uses_canonical_wrappers() {
  local smoke="${ROOT_DIR}/tests/repo_tools/smoke-workflow.sh"
  if ! rg -q "review-pack\\|review-report\\|reviewer-tests" "$smoke"; then
    err "smoke-workflow is missing canonical review wrapper routing case"
  fi
  if ! rg -q "skills/review/scripts/\\$\\{cmd\\}\\.sh" "$smoke"; then
    err "smoke-workflow does not route review wrappers to skills/review/scripts"
  fi
}

check_shim "review-report.sh"
check_shim "review-pack.sh"
check_shim "reviewer-tests.sh"
check_shim "context-pack.sh"
check_shim_runtime_warning "review-report.sh"
check_shim_runtime_warning "review-pack.sh"
check_shim_runtime_warning "reviewer-tests.sh"
check_smoke_uses_canonical_wrappers

if rg -n "\$\{CLAUDE_PLUGIN_ROOT\}/skills" "${ROOT_DIR}/hooks" >/dev/null; then
  err "hooks reference skills/** directly"
fi

exit "$STATUS"
