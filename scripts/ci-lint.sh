#!/usr/bin/env bash
# Repository entrypoint: run repo-only checks, then delegate to payload linters.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PAYLOAD_LINT_ROOT="${ROOT_DIR}/src/claude_workflow_cli/data/payload/aidd"

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
  if ! python3 scripts/prompt-version bump --root "${PROMPT_ROOT}" --prompts analyst --kind agent --lang ru --part patch --dry-run >/dev/null; then
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
  local needs_snapshot=0
  for rel in ".claude" ".claude-plugin" "aidd"; do
    if [[ ! -e "${ROOT_DIR}/${rel}" ]]; then
      needs_snapshot=1
      break
    fi
  done
  if (( needs_snapshot == 1 )); then
    if [[ "${CI:-}" == "true" || "${CI:-}" == "1" || "${CLAUDE_SYNC_PAYLOAD_ON_LINT:-}" == "1" ]]; then
      if [[ -f "scripts/sync-payload.sh" ]]; then
        log "runtime snapshot missing; syncing payload to repo root"
        if ! scripts/sync-payload.sh --direction=to-root; then
          err "payload sync (to-root) failed"
          STATUS=1
          return
        fi
      else
        warn "scripts/sync-payload.sh missing; skipping payload sync"
      fi
    else
      warn "runtime snapshot missing; run scripts/sync-payload.sh --direction=to-root before checking"
    fi
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

run_shellcheck() {
  local root="$1"
  if ! command -v shellcheck >/dev/null 2>&1; then
    warn "shellcheck not found; skipping shell script lint"
    return
  fi
  local SH_FILES=()
  while IFS= read -r -d '' file; do
    SH_FILES+=("$file")
  done < <(find "$root" -type f \( -name "*.sh" -o -name "*.bash" \) -print0)

  local FILTERED=()
  for file in "${SH_FILES[@]}"; do
    if head -n1 "$file" | grep -qE '^#!/usr/bin/env python3'; then
      continue
    fi
    FILTERED+=("$file")
  done

  if ((${#FILTERED[@]} == 0)); then
    log "no shell scripts detected for shellcheck (root: ${root})"
    return
  fi

  log "running shellcheck on ${#FILTERED[@]} files (root: ${root})"
  if ! shellcheck -x -P "$root" "${FILTERED[@]}"; then
    err "shellcheck reported issues"
    STATUS=1
  fi
}

run_markdownlint() {
  local root="$1"
  if ! command -v markdownlint >/dev/null 2>&1; then
    warn "markdownlint not found; skipping markdown lint"
    return
  fi
  local MD_FILES=()
  while IFS= read -r -d '' file; do
    MD_FILES+=("$file")
  done < <(find "$root" -type f -name "*.md" ! -path "*/node_modules/*" -print0)
  if ((${#MD_FILES[@]} == 0)); then
    log "no markdown files detected (root: ${root})"
    return
  fi
  log "running markdownlint on ${#MD_FILES[@]} files (root: ${root})"
  local md_config="${root}/.markdownlint.yaml"
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
  local root="$1"
  if ! command -v yamllint >/dev/null 2>&1; then
    warn "yamllint not found; skipping yaml lint"
    return
  fi
  local YML_FILES=()
  while IFS= read -r -d '' file; do
    YML_FILES+=("$file")
  done < <(find "$root" -type f \( -name "*.yml" -o -name "*.yaml" \) -print0)
  if ((${#YML_FILES[@]} == 0)); then
    log "no yaml files detected (root: ${root})"
    return
  fi
  log "running yamllint on ${#YML_FILES[@]} files (root: ${root})"
  if ! yamllint "${YML_FILES[@]}"; then
    err "yamllint reported issues"
    STATUS=1
  fi
}

run_answer_pattern_check() {
  local root="$1"
  if ! command -v python3 >/dev/null 2>&1; then
    warn "python3 not found; skipping Answer-pattern check"
    return
  fi
  if ! python3 - "$root" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
pattern = re.compile(r"Answer\\s+[0-9]")
answers_header = "## aidd:answers"

violations = []
for path in root.rglob("*"):
    if not path.is_file():
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        continue
    inside_answers = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            inside_answers = stripped.lower() == answers_header
        if pattern.search(line) and not inside_answers:
            violations.append(f"{path.as_posix()}:{line.strip()}")
            break

if violations:
    for entry in violations[:5]:
        print(f"[answer-pattern] {entry}", file=sys.stderr)
    raise SystemExit(1)
PY
  then
    err "found forbidden pattern 'Answer [0-9]' outside AIDD:ANSWERS blocks"
    STATUS=1
    return
  fi
  log "no forbidden Answer-pattern strings detected (root: ${root})"
}

run_payload_linters() {
  if [[ ! -d "${PAYLOAD_LINT_ROOT}" ]]; then
    warn "payload lint root not found: ${PAYLOAD_LINT_ROOT}; skipping payload linters"
    return
  fi
  run_shellcheck "${PAYLOAD_LINT_ROOT}"
  run_markdownlint "${PAYLOAD_LINT_ROOT}"
  run_yamllint "${PAYLOAD_LINT_ROOT}"
  run_answer_pattern_check "${PAYLOAD_LINT_ROOT}"
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
  if ! AIDD_PACK_ENFORCE_BUDGET=1 python3 -m unittest; then
    err "python tests failed"
    STATUS=1
  fi
}

cd "$ROOT_DIR"

run_prompt_lint
run_prompt_version_check
run_payload_sync_check
run_payload_audit
run_payload_linters

run_python_tests

exit "$STATUS"
