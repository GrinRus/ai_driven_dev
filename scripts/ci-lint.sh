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
  local SH_FILES=()
  while IFS= read -r -d '' file; do
    SH_FILES+=("$file")
  done < <(find . -type f \( -name "*.sh" -o -name "*.bash" \) -print0)

  local FILTERED=()
  for file in "${SH_FILES[@]}"; do
    if head -n1 "$file" | grep -qE '^#!/usr/bin/env python3'; then
      continue
    fi
    FILTERED+=("$file")
  done

  if ((${#FILTERED[@]} == 0)); then
    log "no shell scripts detected for shellcheck"
    return
  fi

  log "running shellcheck on ${#FILTERED[@]} files"
  if ! shellcheck "${FILTERED[@]}"; then
    err "shellcheck reported issues"
    STATUS=1
  fi
}

run_markdownlint() {
  if ! command -v markdownlint >/dev/null 2>&1; then
    warn "markdownlint not found; skipping markdown lint"
    return
  fi
  local MD_FILES=()
  while IFS= read -r -d '' file; do
    MD_FILES+=("$file")
  done < <(find . -type f -name "*.md" ! -path "*/node_modules/*" -print0)
  if ((${#MD_FILES[@]} == 0)); then
    log "no markdown files detected"
    return
  fi
  log "running markdownlint on ${#MD_FILES[@]} files"
  local md_config=".markdownlint.yaml"
  if [[ -f "$md_config" ]]; then
    if ! markdownlint --config "$md_config" "${MD_FILES[@]}"; then
      err "markdownlint reported issues"
      STATUS=1
    fi
    return
  fi
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

run_prompt_lint() {
  if ! command -v python3 >/dev/null 2>&1; then
    warn "python3 not found; skipping prompt lint"
    return
  fi
  if [[ ! -f "scripts/lint-prompts.py" ]]; then
    warn "scripts/lint-prompts.py missing; skipping prompt lint"
    return
  fi
  log "running prompt lint"
  if ! python3 scripts/lint-prompts.py; then
    err "prompt lint failed"
    STATUS=1
  fi
}

run_prompt_version_check() {
  if ! command -v python3 >/dev/null 2>&1; then
    warn "python3 not found; skipping prompt-version dry-run"
    return
  fi
  if [[ ! -x "scripts/prompt-version" ]]; then
    warn "scripts/prompt-version missing; skipping"
    return
  fi
  log "running prompt-version dry-run"
  if ! python3 scripts/prompt-version bump --prompts analyst --kind agent --lang ru,en --part patch --dry-run >/dev/null; then
    err "prompt-version dry-run failed"
    STATUS=1
  fi
}

run_payload_sync_check() {
  if ! command -v python3 >/dev/null 2>&1; then
    warn "python3 not found; skipping payload sync check"
    return
  }
  if [[ ! -f "tools/check_payload_sync.py" ]]; then
    warn "tools/check_payload_sync.py missing; skipping payload sync check"
    return
  }
  log "validating payload vs repository snapshots"
  if ! python3 tools/check_payload_sync.py; then
    err "payload sync check failed"
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
run_prompt_lint
run_prompt_version_check
run_payload_sync_check
run_python_tests

exit "$STATUS"
