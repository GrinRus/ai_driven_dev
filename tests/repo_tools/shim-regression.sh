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
  local target_rel="$2"
  local shim_path="${ROOT_DIR}/tools/${tool}"
  local target="${ROOT_DIR}/${target_rel}"

  if [[ ! -f "$shim_path" ]]; then
    err "missing shim: tools/${tool}"
    return
  fi
  if ! rg -q "DEPRECATED" "$shim_path"; then
    err "shim lacks deprecation notice: tools/${tool}"
  fi
  if ! rg -q "exec .*${target_rel}" "$shim_path"; then
    err "shim does not exec ${target_rel}"
  fi
  if [[ ! -x "$target" ]]; then
    err "skill script not executable: ${target_rel}"
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

check_hook_dual_path_hints() {
  local gate_qa="${ROOT_DIR}/hooks/gate-qa.sh"
  local gate_tests="${ROOT_DIR}/hooks/gate-tests.sh"
  if ! rg -q "skills/qa/scripts/qa.sh" "$gate_qa"; then
    err "gate-qa hint is missing canonical qa path"
  fi
  if ! rg -q "tools/qa.sh" "$gate_qa"; then
    err "gate-qa hint is missing legacy qa shim path"
  fi
  if ! rg -q "DEPRECATED" "$gate_qa"; then
    err "gate-qa hint must mark legacy shim as DEPRECATED"
  fi
  if ! rg -q "skills/researcher/scripts/research.sh" "$gate_tests"; then
    err "gate-tests hint is missing canonical research path"
  fi
  if ! rg -q "tools/research.sh" "$gate_tests"; then
    err "gate-tests hint is missing legacy research shim path"
  fi
  if ! rg -q "DEPRECATED" "$gate_tests"; then
    err "gate-tests hint must mark legacy shim as DEPRECATED"
  fi
}

check_shim "review-report.sh" "skills/review/scripts/review-report.sh"
check_shim "review-pack.sh" "skills/review/scripts/review-pack.sh"
check_shim "reviewer-tests.sh" "skills/review/scripts/reviewer-tests.sh"
check_shim "context-pack.sh" "skills/review/scripts/context-pack.sh"
check_shim "analyst-check.sh" "skills/idea-new/scripts/analyst-check.sh"
check_shim "research-check.sh" "skills/plan-new/scripts/research-check.sh"
check_shim "prd-review.sh" "skills/review-spec/scripts/prd-review.sh"
check_shim "research.sh" "skills/researcher/scripts/research.sh"
check_shim "reports-pack.sh" "skills/researcher/scripts/reports-pack.sh"
check_shim "rlm-nodes-build.sh" "skills/researcher/scripts/rlm-nodes-build.sh"
check_shim "rlm-verify.sh" "skills/researcher/scripts/rlm-verify.sh"
check_shim "rlm-links-build.sh" "skills/researcher/scripts/rlm-links-build.sh"
check_shim "rlm-jsonl-compact.sh" "skills/researcher/scripts/rlm-jsonl-compact.sh"
check_shim "rlm-finalize.sh" "skills/researcher/scripts/rlm-finalize.sh"
check_shim "qa.sh" "skills/qa/scripts/qa.sh"
check_shim "status.sh" "skills/status/scripts/status.sh"
check_shim "index-sync.sh" "skills/status/scripts/index-sync.sh"
check_shim_runtime_warning "review-report.sh"
check_shim_runtime_warning "review-pack.sh"
check_shim_runtime_warning "reviewer-tests.sh"
check_shim_runtime_warning "analyst-check.sh"
check_shim_runtime_warning "research-check.sh"
check_shim_runtime_warning "prd-review.sh"
check_shim_runtime_warning "research.sh"
check_shim_runtime_warning "reports-pack.sh"
check_shim_runtime_warning "rlm-nodes-build.sh"
check_shim_runtime_warning "rlm-verify.sh"
check_shim_runtime_warning "rlm-links-build.sh"
check_shim_runtime_warning "rlm-jsonl-compact.sh"
check_shim_runtime_warning "rlm-finalize.sh"
check_shim_runtime_warning "qa.sh"
check_shim_runtime_warning "status.sh"
check_shim_runtime_warning "index-sync.sh"
check_smoke_uses_canonical_wrappers
check_hook_dual_path_hints

exit "$STATUS"
