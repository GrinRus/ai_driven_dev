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

PROMPT_ROOT="${ROOT_DIR}"

run_bash_check() {
  local script="$1"
  local label="$2"
  local fail_msg="$3"
  if [[ ! -f "${script}" ]]; then
    warn "${script} missing; skipping"
    return
  fi
  log "running ${label}"
  if ! bash "${script}"; then
    err "${fail_msg}"
    STATUS=1
  fi
}

run_python_check() {
  local script="$1"
  local label="$2"
  local fail_msg="$3"
  shift 3
  if ! command -v python3 >/dev/null 2>&1; then
    warn "python3 not found; skipping ${label}"
    return
  fi
  if [[ ! -f "${script}" ]]; then
    warn "${script} missing; skipping"
    return
  fi
  log "running ${label}"
  if ! python3 "${script}" "$@"; then
    err "${fail_msg}"
    STATUS=1
  fi
}

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

run_e2e_prompt_build_guard() {
  if ! command -v python3 >/dev/null 2>&1; then
    warn "python3 not found; skipping e2e prompt build guard"
    return
  fi
  if [[ ! -f "tests/repo_tools/build_e2e_prompts.py" ]]; then
    warn "tests/repo_tools/build_e2e_prompts.py missing; skipping e2e prompt build guard"
    return
  fi
  log "running e2e prompt build guard"
  if ! python3 tests/repo_tools/build_e2e_prompts.py --check; then
    err "e2e prompt render check failed; run tests/repo_tools/build_e2e_prompts.py --output-dir <dir>"
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
  if ! python3 tests/repo_tools/prompt-version bump --root "${PROMPT_ROOT}" --prompts analyst --kind agent --lang en --part patch --dry-run >/dev/null; then
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
  local tmp_output
  tmp_output="$(mktemp "${TMPDIR:-/tmp}/aidd-entrypoints-bundle.XXXXXX")"
  trap 'rm -f "${tmp_output}"' RETURN
  if ! python3 tests/repo_tools/entrypoints_bundle.py --root "${ROOT_DIR}" --output "${tmp_output}"; then
    err "entrypoints bundle generation failed"
    STATUS=1
    rm -f "${tmp_output}"
    return
  fi
  if ! python3 - "${tmp_output}" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
required = {"schema", "skills", "agents"}
missing = sorted(required - payload.keys())
if missing:
    raise SystemExit(f"missing keys: {missing}")
PY
  then
    err "entrypoints bundle validation failed"
    STATUS=1
  fi
  rm -f "${tmp_output}"
  trap - RETURN
}


run_skill_eval_smoke() {
  local enforce="${AIDD_SKILL_EVAL_ENFORCE:-0}"
  if ! command -v python3 >/dev/null 2>&1; then
    if [[ "${enforce}" == "1" ]]; then
      err "python3 not found under skill eval enforcement"
      STATUS=1
      return
    fi
    warn "python3 not found; skipping skill eval smoke"
    return
  fi
  if [[ ! -f "tests/repo_tools/skill_eval_run.py" ]]; then
    if [[ "${enforce}" == "1" ]]; then
      err "tests/repo_tools/skill_eval_run.py missing under skill eval enforcement"
      STATUS=1
      return
    fi
    warn "tests/repo_tools/skill_eval_run.py missing; skipping skill eval smoke"
    return
  fi
  if [[ ! -f "tests/repo_tools/skill_eval/cases.v1.jsonl" ]]; then
    if [[ "${enforce}" == "1" ]]; then
      err "skill eval dataset missing under skill eval enforcement"
      STATUS=1
      return
    fi
    warn "skill eval dataset missing; skipping skill eval smoke"
    return
  fi

  local out_dir="aidd/reports/events/skill-eval"

  log "running skill eval smoke (38 cases, advisory by default)"
  if ! python3 tests/repo_tools/skill_eval_run.py \
    --cases tests/repo_tools/skill_eval/cases.v1.jsonl \
    --max-cases 38 \
    --seed 104 \
    --out-dir "${out_dir}"; then
    if [[ "${enforce}" == "1" ]]; then
      err "skill eval smoke failed under enforcement"
      STATUS=1
      return
    fi
    warn "skill eval smoke failed (advisory mode)"
    return
  fi

  if [[ ! -f "tests/repo_tools/skill_eval_compare.py" ]]; then
    if [[ "${enforce}" == "1" ]]; then
      err "tests/repo_tools/skill_eval_compare.py missing under skill eval enforcement"
      STATUS=1
      return
    fi
    warn "tests/repo_tools/skill_eval_compare.py missing; skipping skill eval comparator"
    return
  fi

  local baseline="${AIDD_SKILL_EVAL_BASELINE:-}"
  if [[ -z "${baseline}" || ! -f "${baseline}" ]]; then
    if [[ "${enforce}" == "1" ]]; then
      err "skill eval baseline is required under enforcement"
      STATUS=1
      return
    fi
    log "skill eval baseline not configured; skipping comparator"
    return
  fi

  local candidate
  candidate="$(
    find "${out_dir}" -type f -path "*/run-*/summary.json" -print 2>/dev/null \
      | sort \
      | tail -n 1 || true
  )"
  if [[ -z "${candidate}" || ! -f "${candidate}" ]]; then
    if [[ "${enforce}" == "1" ]]; then
      err "skill eval candidate summary missing under enforcement"
      STATUS=1
      return
    fi
    warn "skill eval candidate summary not found; skipping comparator"
    return
  fi

  local delta_path="${out_dir}/compare.latest.json"
  if ! python3 tests/repo_tools/skill_eval_compare.py \
    --baseline "${baseline}" \
    --candidate "${candidate}" \
    --out "${delta_path}"; then
    if [[ "${enforce}" == "1" ]]; then
      err "skill eval comparator failed under enforcement"
      STATUS=1
      return
    fi
    warn "skill eval comparator failed (advisory mode)"
    return
  fi
}

run_research_legacy_artifact_guard() {
  if ! command -v rg >/dev/null 2>&1; then
    warn "rg not found; skipping research legacy artifact guard"
    return
  fi
  log "running research legacy artifact guard"
  local legacy_paths='reports/research/[^/]+-context\.json|reports/research/[^/]+-targets\.json'
  local scan_roots=(skills hooks templates docs)
  if [[ -d "dev" ]]; then
    scan_roots+=(dev)
  fi
  if rg -n "${legacy_paths}" "${scan_roots[@]}" | rg -v "rlm-targets\.json" >/dev/null; then
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

run_ruff_hygiene() {
  local -a ruff_cmd=()
  if command -v ruff >/dev/null 2>&1; then
    ruff_cmd=(ruff)
  elif python3 -m ruff --version >/dev/null 2>&1; then
    ruff_cmd=(python3 -m ruff)
  elif python3 -m pip --version >/dev/null 2>&1; then
    log "ruff not found; installing user-local copy"
    if ! python3 -m pip install --user ruff >/dev/null; then
      err "failed to install ruff for hygiene checks"
      STATUS=1
      return
    fi
    export PATH="${HOME}/.local/bin:${PATH}"
    if command -v ruff >/dev/null 2>&1; then
      ruff_cmd=(ruff)
    elif python3 -m ruff --version >/dev/null 2>&1; then
      ruff_cmd=(python3 -m ruff)
    fi
  fi
  if ((${#ruff_cmd[@]} == 0)); then
    err "ruff is required for hygiene checks"
    STATUS=1
    return
  fi
  log "running ruff hygiene checks"
  if ! "${ruff_cmd[@]}" check . --select F401,F821,F841,B007,B023,ERA; then
    err "ruff hygiene checks failed"
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

blocked = re.compile(
    r"^(main|master|develop|codex/wave[^/]*|feature/.+|codex/feature/.+)$"
)
release_tag = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
violations = []
for plugin in payload.get("plugins", []) or []:
    if not isinstance(plugin, dict):
        continue
    source = plugin.get("source") if isinstance(plugin.get("source"), dict) else {}
    ref = str(source.get("ref") or "").strip()
    name = str(plugin.get("name") or "unknown")
    if ref and blocked.match(ref):
        violations.append((name, ref))
        continue
    if not release_tag.match(ref):
        print(
            f"[marketplace-ref] {name}: ref must be immutable release tag vX.Y.Z (got '{ref}')",
            file=sys.stderr,
        )
        raise SystemExit(1)

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
    ! -path "${root}/aidd/*" \
    ! -path "${root}/.aidd_audit/*" \
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
    ! -path "${root}/aidd/*" \
    ! -path "${root}/.aidd_audit/*" \
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
  done < <(find "$root" -type f \( -name "*.yml" -o -name "*.yaml" \) \
    ! -path "${root}/aidd/*" \
    ! -path "${root}/.aidd_audit/*" \
    -print0)
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

run_legacy_qna_pattern_check() {
  local root="$1"
  if ! command -v python3 >/dev/null 2>&1; then
    warn "python3 not found; skipping legacy Qn-pattern check"
    return
  fi
  if ! python3 - "$root" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
pattern = re.compile(r"\b(?:Answer|Ответ)\s+[0-9]+\s*:")
target_globs = [
    "skills/*/templates/*",
    "tests/repo_tools/e2e_prompt/*.md",
    "tests/repo_tools/smoke-workflow.sh",
]

targets = set()
for glob_pattern in target_globs:
    for path in root.glob(glob_pattern):
        if path.is_file():
            targets.add(path)

violations = []
for path in sorted(targets):
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        continue
    for lineno, line in enumerate(text.splitlines(), start=1):
        if pattern.search(line):
            violations.append(f"{path.as_posix()}:{lineno}:{line.strip()}")
            break

if violations:
    for entry in violations[:5]:
        print(f"[legacy-qna-pattern] {entry}", file=sys.stderr)
    raise SystemExit(1)
PY
  then
    err "found forbidden legacy Qn tokens ('Answer N:' / 'Ответ N:') in canonical templates/prompts/smoke"
    STATUS=1
    return
  fi
  log "no forbidden legacy Qn tokens detected (root: ${root})"
}

run_repo_linters() {
  if [[ ! -d "${LINT_ROOT}" ]]; then
    warn "lint root not found: ${LINT_ROOT}; skipping linters"
    return
  fi
  run_shellcheck "${LINT_ROOT}"
  run_markdownlint "${LINT_ROOT}"
  run_yamllint "${LINT_ROOT}"
  run_legacy_qna_pattern_check "${LINT_ROOT}"
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

run_e2e_prompt_build_guard
run_prompt_lint
run_prompt_version_check
run_prompt_sync_guard
run_entrypoints_bundle_guard
run_bash_check "tests/repo_tools/prompt-regression.sh" "prompt regression checks" "prompt regression checks failed"
run_skill_eval_smoke
run_bash_check "tests/repo_tools/loop-regression.sh" "loop regression checks" "loop regression checks failed"
run_bash_check "tests/repo_tools/output-contract-regression.sh" "output contract regression checks" "output contract regression checks failed"
run_bash_check "tests/repo_tools/claude-stream-render" "claude stream renderer checks" "claude stream renderer checks failed"
run_bash_check "tests/repo_tools/tool-result-id" "tool-result id checks" "tool-result id checks failed"
run_python_check "tests/repo_tools/skill-scripts-guard.py" "skill scripts guard" "skill scripts guard failed"
run_python_check "tests/repo_tools/bash-runtime-guard.py" "bash runtime guard" "bash runtime guard failed"
run_bash_check "tests/repo_tools/schema-guards.sh" "schema + contract guards" "schema + contract guards failed"
run_bash_check "tests/repo_tools/runtime-path-regression.sh" "runtime path regression checks (python-only canon)" "runtime path regression checks failed"
run_research_legacy_artifact_guard
run_python_check "tests/repo_tools/runtime-module-guard.py" "runtime module guard" "runtime module guard failed"
run_python_check "tests/repo_tools/runtime-bootstrap-guard.py" "runtime bootstrap guard" "runtime bootstrap guard failed" --root "$ROOT_DIR"
run_python_check "tests/repo_tools/cli-adapter-guard.py" "cli adapter guard" "cli adapter guard failed"
run_bash_check "tests/repo_tools/python-only-regression.sh" "python-only regression checks" "python-only regression checks failed"
run_python_check "tests/repo_tools/release_guard.py" "release guard" "release guard failed" --root "${ROOT_DIR}"
run_python_check "tests/repo_tools/release_docs_guard.py" "release docs guard" "release docs guard failed" --root "${ROOT_DIR}"
run_ruff_hygiene
run_python_check "tests/repo_tools/docs_hygiene_guard.py" "docs hygiene guard" "docs hygiene guard failed"
run_marketplace_ref_guard
run_repo_linters

run_python_tests

exit "$STATUS"
