#!/usr/bin/env bash
# Repository entrypoint: run repo checks and linters.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LINT_ROOT="${ROOT_DIR}"

STATUS=0
export PYTHONDONTWRITEBYTECODE=1

log()  { printf '[info] %s\n' "$*"; }
warn() { printf '[warn] %s\n' "$*" >&2; }
err()  { printf '[error] %s\n' "$*" >&2; }

resolve_prompt_root() {
  if [[ -d "${ROOT_DIR}/agents" || -d "${ROOT_DIR}/commands" ]]; then
    printf '%s' "${ROOT_DIR}"
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
  if [[ ! -f "tests/repo_tools/lint-prompts.py" ]]; then
    warn "tests/repo_tools/lint-prompts.py missing; skipping prompt lint"
    return
  fi
  log "running prompt lint (root: ${PROMPT_ROOT})"
  if ! python3 tests/repo_tools/lint-prompts.py --root "${PROMPT_ROOT}"; then
    err "prompt lint failed"
    STATUS=1
  fi
}

run_prompt_version_check() {
  if ! command -v python3 >/dev/null 2>&1; then
    warn "python3 not found; skipping prompt-version dry-run"
    return
  fi
  if [[ ! -f "tests/repo_tools/prompt-version" ]]; then
    warn "tests/repo_tools/prompt-version missing; skipping"
    return
  fi
  log "running prompt-version dry-run (root: ${PROMPT_ROOT})"
  if ! python3 tests/repo_tools/prompt-version bump --root "${PROMPT_ROOT}" --prompts analyst --kind agent --lang ru --part patch --dry-run >/dev/null; then
    err "prompt-version dry-run failed"
    STATUS=1
  fi
}

run_prompt_sync_guard() {
  if ! command -v python3 >/dev/null 2>&1; then
    warn "python3 not found; skipping prompt/template sync guard"
    return
  fi
  if [[ ! -f "tools/prompt_template_sync.py" ]]; then
    warn "tools/prompt_template_sync.py missing; skipping"
    return
  fi
  log "running prompt/template sync guard (root: ${ROOT_DIR})"
  local cmd=(python3 tools/prompt_template_sync.py --root "${ROOT_DIR}")
  if [[ -n "${AIDD_PAYLOAD_ROOT:-}" ]]; then
    cmd+=(--payload-root "${AIDD_PAYLOAD_ROOT}")
  fi
  if ! "${cmd[@]}"; then
    err "prompt/template sync guard failed"
    STATUS=1
  fi
}

run_prompt_regression() {
  if [[ ! -f "tests/repo_tools/prompt-regression.sh" ]]; then
    warn "tests/repo_tools/prompt-regression.sh missing; skipping"
    return
  fi
  log "running prompt regression checks"
  if ! bash tests/repo_tools/prompt-regression.sh; then
    err "prompt regression checks failed"
    STATUS=1
  fi
}

run_loop_regression() {
  if [[ ! -f "tests/repo_tools/loop-regression.sh" ]]; then
    warn "tests/repo_tools/loop-regression.sh missing; skipping"
    return
  fi
  log "running loop regression checks"
  if ! bash tests/repo_tools/loop-regression.sh; then
    err "loop regression checks failed"
    STATUS=1
  fi
}
run_arch_profile_validate() {
  if ! command -v python3 >/dev/null 2>&1; then
    warn "python3 not found; skipping arch profile validate"
    return
  fi
  if [[ ! -f "tools/arch-profile-validate.sh" ]]; then
    warn "tools/arch-profile-validate.sh missing; skipping"
    return
  fi
  log "running arch profile validation (template)"
  if ! python3 tools/arch-profile-validate.sh --path templates/aidd/docs/architecture/profile.md; then
    err "arch profile validation failed"
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
  done < <(find "$root" -type f \( -name "*.sh" -o -name "*.bash" \) \
    ! -path "*/build/*" \
    ! -path "*/.git/*" \
    -print0)

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
  done < <(find "$root" -type f -name "*.md" \
    ! -path "*/node_modules/*" \
    ! -path "*/build/*" \
    ! -path "*/.git/*" \
    -print0)
  local FILTERED=()
  for file in "${MD_FILES[@]}"; do
    case "$file" in
      */backlog.md|*/CHANGELOG.md)
        continue
        ;;
    esac
    FILTERED+=("$file")
  done
  MD_FILES=("${FILTERED[@]}")
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

run_repo_linters() {
  if [[ ! -d "${LINT_ROOT}" ]]; then
    warn "lint root not found: ${LINT_ROOT}; skipping linters"
    return
  fi
  run_shellcheck "${LINT_ROOT}"
  run_markdownlint "${LINT_ROOT}"
  run_yamllint "${LINT_ROOT}"
  run_answer_pattern_check "${LINT_ROOT}"
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
  if ! AIDD_PACK_ENFORCE_BUDGET=1 python3 -m unittest discover -s tests -t .; then
    err "python tests failed"
    STATUS=1
  fi
}

cd "$ROOT_DIR"

run_prompt_lint
run_prompt_version_check
run_prompt_sync_guard
run_prompt_regression
run_loop_regression
run_arch_profile_validate
run_repo_linters

run_python_tests

exit "$STATUS"
