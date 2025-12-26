#!/usr/bin/env bash
# Repository entrypoint: run repo-only checks, then delegate to payload linters.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PAYLOAD_SCRIPT="${ROOT_DIR}/src/claude_workflow_cli/data/payload/aidd/scripts/ci-lint.sh"

STATUS=0
export PYTHONDONTWRITEBYTECODE=1

log()  { printf '[info] %s\n' "$*"; }
warn() { printf '[warn] %s\n' "$*" >&2; }
err()  { printf '[error] %s\n' "$*" >&2; }

resolve_prompt_root() {
  local candidate
  candidate="${ROOT_DIR}/aidd"
  if [[ -d "${candidate}/agents" || -d "${candidate}/commands" ]]; then
    printf '%s' "${candidate}"
    return
  fi
  candidate="${ROOT_DIR}/src/claude_workflow_cli/data/payload/aidd"
  if [[ -d "${candidate}/agents" || -d "${candidate}/commands" ]]; then
    printf '%s' "${candidate}"
    return
  fi
  printf '%s' "${ROOT_DIR}"
}

PROMPT_ROOT="$(resolve_prompt_root)"

run_prompt_lint() {
  if ! command -v python3 >/dev/null 2>&1; then
    warn "python3 not found; skipping prompt lint"
    return
  fi
  if [[ ! -f "scripts/lint-prompts.py" ]]; then
    warn "scripts/lint-prompts.py missing; skipping prompt lint"
    return
  fi
  log "running prompt lint (root: ${PROMPT_ROOT})"
  if ! python3 scripts/lint-prompts.py --root "${PROMPT_ROOT}"; then
    err "prompt lint failed"
    STATUS=1
  fi
}

run_prompt_version_check() {
  if ! command -v python3 >/dev/null 2>&1; then
    warn "python3 not found; skipping prompt-version dry-run"
    return
  fi
  if [[ ! -f "scripts/prompt-version" ]]; then
    warn "scripts/prompt-version missing; skipping"
    return
  fi
  log "running prompt-version dry-run (root: ${PROMPT_ROOT})"
  if ! python3 scripts/prompt-version bump --root "${PROMPT_ROOT}" --prompts analyst --kind agent --lang ru,en --part patch --dry-run >/dev/null; then
    err "prompt-version dry-run failed"
    STATUS=1
  fi
}

run_payload_sync_check() {
  if ! command -v python3 >/dev/null 2>&1; then
    warn "python3 not found; skipping payload sync check"
    return
  fi
  if [[ ! -f "tools/check_payload_sync.py" ]]; then
    warn "tools/check_payload_sync.py missing; skipping payload sync check"
    return
  fi
  log "validating payload vs repository snapshots"
  if ! python3 tools/check_payload_sync.py; then
    err "payload sync check failed"
    STATUS=1
  fi
}

run_payload_audit() {
  if ! command -v python3 >/dev/null 2>&1; then
    warn "python3 not found; skipping payload audit"
    return
  fi
  if [[ ! -f "tools/payload_audit.py" ]]; then
    warn "tools/payload_audit.py missing; skipping payload audit"
    return
  fi
  log "auditing payload contents"
  if ! python3 tools/payload_audit.py; then
    err "payload audit failed"
    STATUS=1
  fi
}

run_python_tests() {
  if ! command -v python3 >/dev/null 2>&1; then
    warn "python3 not found; skipping tests"
    return
  fi
  if [[ ! -d "tests" ]]; then
    log "tests/ directory not found; skipping python tests"
    return
  fi
  log "running python unittest suite"
  if ! python3 -m unittest; then
    err "python tests failed"
    STATUS=1
  fi
}

cd "$ROOT_DIR"

run_prompt_lint
run_prompt_version_check
run_payload_sync_check
run_payload_audit

if [[ ! -x "${PAYLOAD_SCRIPT}" ]]; then
  err "payload ci-lint script not found: ${PAYLOAD_SCRIPT}"
  exit 1
fi

log "running payload ci-lint"
export CLAUDE_PROJECT_DIR="${ROOT_DIR}"
if ! "${PAYLOAD_SCRIPT}" "$@"; then
  err "payload ci-lint failed"
  STATUS=1
fi

run_python_tests

exit "$STATUS"
