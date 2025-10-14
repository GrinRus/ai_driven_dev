#!/usr/bin/env bash
# scripts/ci-lint.sh
# Unified entrypoint for running linters and tests locally or in CI.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

STATUS=0

log()  { printf '[info] %s\n' "$*"; }
warn() { printf '[warn] %s\n' "$*" >&2; }
err()  { printf '[error] %s\n' "$*" >&2; }

run_shellcheck() {
  if ! command -v shellcheck >/dev/null 2>&1; then
    warn "shellcheck not found; skipping shell script lint"
    return
  fi
  mapfile -d '' -t SH_FILES < <(find . -type f \( -name "*.sh" -o -name "*.bash" \) -print0)
  if ((${#SH_FILES[@]} == 0)); then
    log "no shell scripts detected for shellcheck"
    return
  fi
  log "running shellcheck on ${#SH_FILES[@]} files"
  if ! shellcheck "${SH_FILES[@]}"; then
    err "shellcheck reported issues"
    STATUS=1
  fi
}

run_markdownlint() {
  if ! command -v markdownlint >/dev/null 2>&1; then
    warn "markdownlint not found; skipping markdown lint"
    return
  fi
  mapfile -d '' -t MD_FILES < <(find . -type f -name "*.md" ! -path "*/node_modules/*" -print0)
  if ((${#MD_FILES[@]} == 0)); then
    log "no markdown files detected"
    return
  fi
  log "running markdownlint on ${#MD_FILES[@]} files"
  if ! markdownlint "${MD_FILES[@]}"; then
    err "markdownlint reported issues"
    STATUS=1
  fi
}

run_yamllint() {
  if ! command -v yamllint >/dev/null 2>&1; then
    warn "yamllint not found; skipping yaml lint"
    return
  fi
  local YML_FILES=()
  while IFS= read -r -d '' file; do
    YML_FILES+=("$file")
  done < <(find . -type f \( -name "*.yml" -o -name "*.yaml" \) -print0)
  if ((${#YML_FILES[@]} == 0)); then
    log "no yaml files detected"
    return
  fi
  log "running yamllint on ${#YML_FILES[@]} files"
  if ! yamllint "${YML_FILES[@]}"; then
    err "yamllint reported issues"
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

run_shellcheck
run_markdownlint
run_yamllint
run_python_tests

exit "$STATUS"
