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
  if ! AIDD_BASH_LEGACY_POLICY="${AIDD_BASH_LEGACY_POLICY:-error}" \
    python3 tests/repo_tools/lint-prompts.py --root "${PROMPT_ROOT}"; then
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
  if [[ ! -f "tests/repo_tools/prompt_template_sync.py" ]]; then
    warn "tests/repo_tools/prompt_template_sync.py missing; skipping"
    return
  fi
  log "running prompt/template sync guard (root: ${ROOT_DIR})"
  local cmd=(python3 tests/repo_tools/prompt_template_sync.py --root "${ROOT_DIR}")
  if [[ -n "${AIDD_PAYLOAD_ROOT:-}" ]]; then
    cmd+=(--payload-root "${AIDD_PAYLOAD_ROOT}")
  fi
  if ! "${cmd[@]}"; then
    err "prompt/template sync guard failed"
    STATUS=1
  fi
}


run_entrypoints_bundle_guard() {
  if ! command -v python3 >/dev/null 2>&1; then
    warn "python3 not found; skipping entrypoints bundle guard"
    return
  fi
  if [[ ! -f "tests/repo_tools/entrypoints_bundle.py" ]]; then
    warn "tests/repo_tools/entrypoints_bundle.py missing; skipping"
    return
  fi
  log "running entrypoints bundle guard"
  if ! python3 tests/repo_tools/entrypoints_bundle.py --root "${ROOT_DIR}"; then
    err "entrypoints bundle generation failed"
    STATUS=1
    return
  fi
  if ! git diff --exit-code -- "${ROOT_DIR}/tests/repo_tools/entrypoints-bundle.txt" >/dev/null; then
    err "entrypoints-bundle.txt out of date; rerun tests/repo_tools/entrypoints_bundle.py"
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

run_output_contract_regression() {
  if [[ ! -f "tests/repo_tools/output-contract-regression.sh" ]]; then
    warn "tests/repo_tools/output-contract-regression.sh missing; skipping"
    return
  fi
  log "running output contract regression checks"
  if ! bash tests/repo_tools/output-contract-regression.sh; then
    err "output contract regression checks failed"
    STATUS=1
  fi
}

run_claude_stream_renderer() {
  if [[ ! -f "tests/repo_tools/claude-stream-render" ]]; then
    warn "tests/repo_tools/claude-stream-render missing; skipping"
    return
  fi
  log "running claude stream renderer checks"
  if ! bash tests/repo_tools/claude-stream-render; then
    err "claude stream renderer checks failed"
    STATUS=1
  fi
}

run_tool_result_id_check() {
  if [[ ! -f "tests/repo_tools/tool-result-id" ]]; then
    warn "tests/repo_tools/tool-result-id missing; skipping"
    return
  fi
  log "running tool-result id checks"
  if ! bash tests/repo_tools/tool-result-id; then
    err "tool-result id checks failed"
    STATUS=1
  fi
}

run_skill_scripts_guard() {
  if ! command -v python3 >/dev/null 2>&1; then
    warn "python3 not found; skipping skill scripts guard"
    return
  fi
  if [[ ! -f "tests/repo_tools/skill-scripts-guard.py" ]]; then
    warn "tests/repo_tools/skill-scripts-guard.py missing; skipping"
    return
  fi
  log "running skill scripts guard"
  if ! python3 tests/repo_tools/skill-scripts-guard.py; then
    err "skill scripts guard failed"
    STATUS=1
  fi
}

run_bash_runtime_guard() {
  if ! command -v python3 >/dev/null 2>&1; then
    warn "python3 not found; skipping bash runtime guard"
    return
  fi
  if [[ ! -f "tests/repo_tools/bash-runtime-guard.py" ]]; then
    warn "tests/repo_tools/bash-runtime-guard.py missing; skipping"
    return
  fi
  log "running bash runtime guard"
  if ! python3 tests/repo_tools/bash-runtime-guard.py; then
    err "bash runtime guard failed"
    STATUS=1
  fi
}

run_schema_guards() {
  if [[ ! -f "tests/repo_tools/schema-guards.sh" ]]; then
    warn "tests/repo_tools/schema-guards.sh missing; skipping"
    return
  fi
  log "running schema + contract guards"
  if ! bash tests/repo_tools/schema-guards.sh; then
    err "schema + contract guards failed"
    STATUS=1
  fi
}

run_runtime_path_regression() {
  if [[ ! -f "tests/repo_tools/runtime-path-regression.sh" ]]; then
    warn "tests/repo_tools/runtime-path-regression.sh missing; skipping"
    return
  fi
  log "running runtime path regression checks (python-only canon)"
  if ! bash tests/repo_tools/runtime-path-regression.sh; then
    err "runtime path regression checks failed"
    STATUS=1
  fi
}

run_research_legacy_artifact_guard() {
  if ! command -v rg >/dev/null 2>&1; then
    warn "rg not found; skipping research legacy artifact guard"
    return
  fi
  log "running research legacy artifact guard"
  local legacy_paths='reports/research/[^/]+-context\.json|reports/research/[^/]+-targets\.json'
  if rg -n "${legacy_paths}" skills hooks templates docs dev | rg -v "rlm-targets\.json" >/dev/null; then
    err "legacy research artifact refs found in runtime/docs surfaces"
    STATUS=1
  fi
  if rg -n "${legacy_paths}" tests | rg -v "rlm-targets\.json" | rg -v "fixtures|compat" >/dev/null; then
    err "legacy research artifact refs found in tests outside compat fixtures"
    STATUS=1
  fi
  if rg -n "context\\.json|targets\\.json" skills hooks templates | rg -v "rlm-targets\\.json" >/dev/null; then
    err "runtime write/read surfaces still reference legacy context/targets artifacts"
    STATUS=1
  fi
}

run_runtime_module_guard() {
  if ! command -v python3 >/dev/null 2>&1; then
    warn "python3 not found; skipping runtime module guard"
    return
  fi
  if [[ ! -f "tests/repo_tools/runtime-module-guard.py" ]]; then
    warn "tests/repo_tools/runtime-module-guard.py missing; skipping"
    return
  fi
  log "running runtime module guard"
  if ! python3 tests/repo_tools/runtime-module-guard.py; then
    err "runtime module guard failed"
    STATUS=1
  fi
}

run_python_only_regression() {
  if [[ ! -f "tests/repo_tools/python-only-regression.sh" ]]; then
    warn "tests/repo_tools/python-only-regression.sh missing; skipping"
    return
  fi
  log "running python-only regression checks"
  if ! bash tests/repo_tools/python-only-regression.sh; then
    err "python-only regression checks failed"
    STATUS=1
  fi
}

run_marketplace_ref_guard() {
  if ! command -v python3 >/dev/null 2>&1; then
    warn "python3 not found; skipping marketplace ref guard"
    return
  fi
  if [[ ! -f ".claude-plugin/marketplace.json" ]]; then
    log "marketplace manifest not found; skipping ref guard"
    return
  fi
  log "running marketplace ref guard"
  if ! python3 - <<'PY'
import json
import re
import sys
from pathlib import Path

path = Path(".claude-plugin/marketplace.json")
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    print(f"[marketplace-ref] invalid marketplace.json: {exc}", file=sys.stderr)
    raise SystemExit(1)

blocked = re.compile(r"^(codex/wave[^/]*|feature/.+|codex/feature/.+)$")
violations = []
for plugin in payload.get("plugins", []) or []:
    if not isinstance(plugin, dict):
        continue
    source = plugin.get("source") if isinstance(plugin.get("source"), dict) else {}
    ref = str(source.get("ref") or "").strip()
    name = str(plugin.get("name") or "unknown")
    if ref and blocked.match(ref):
        violations.append((name, ref))

if violations:
    for name, ref in violations:
        print(f"[marketplace-ref] {name}: forbidden unstable ref '{ref}'", file=sys.stderr)
    raise SystemExit(1)
PY
  then
    err "marketplace ref guard failed"
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
      */backlog.md|*/CHANGELOG.md|*/aidd_audit_report.md|*/aidd_improvement_plan.md)
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
  if ! python3 -m pytest --version >/dev/null 2>&1; then
    err "pytest is required for repo checks (python3 -m pytest not available)"
    STATUS=1
    return
  fi
  log "running python pytest suite"
  if ! AIDD_PACK_ENFORCE_BUDGET=1 python3 -m pytest -q tests; then
    err "python pytest suite failed"
    STATUS=1
  fi
}

cd "$ROOT_DIR"

run_prompt_lint
run_prompt_version_check
run_prompt_sync_guard
run_entrypoints_bundle_guard
run_prompt_regression
run_loop_regression
run_output_contract_regression
run_claude_stream_renderer
run_tool_result_id_check
run_skill_scripts_guard
run_bash_runtime_guard
run_schema_guards
run_runtime_path_regression
run_research_legacy_artifact_guard
run_runtime_module_guard
run_python_only_regression
run_marketplace_ref_guard
run_repo_linters

run_python_tests

exit "$STATUS"
