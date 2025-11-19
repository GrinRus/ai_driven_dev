#!/usr/bin/env bash
# scripts/prompt-release.sh
# Automate prompt version bumps + validation before publishing payload/release.
set -euo pipefail

PART="patch"
DRY_RUN=0
PROMPTS="all"
KIND="both"
LANGS="ru,en"

usage() {
  cat <<'EOF'
Usage: scripts/prompt-release.sh [options]
  --part LEVEL        semver segment to bump (major|minor|patch, default: patch)
  --prompts LIST      comma-separated prompt names or 'all'
  --kind TYPE         agent | command | both (default: both)
  --langs LIST        comma-separated locales (default: ru,en)
  --dry-run           compute bumps without changing files (prompt-version dry-run)
  -h, --help          show this help message

The script runs:
  1. scripts/prompt-version bump ...
  2. scripts/lint-prompts.py
  3. pytest suite for prompt tests
  4. tools/check_payload_sync.py
  5. pytest gate workflow tests
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --part)
      [[ $# -ge 2 ]] || { echo "--part requires a value" >&2; exit 1; }
      PART="$2"; shift 2;;
    --prompts)
      [[ $# -ge 2 ]] || { echo "--prompts requires a value" >&2; exit 1; }
      PROMPTS="$2"; shift 2;;
    --kind)
      [[ $# -ge 2 ]] || { echo "--kind requires a value" >&2; exit 1; }
      KIND="$2"; shift 2;;
    --langs)
      [[ $# -ge 2 ]] || { echo "--langs requires a value" >&2; exit 1; }
      LANGS="$2"; shift 2;;
    --dry-run)
      DRY_RUN=1; shift;;
    -h|--help)
      usage; exit 0;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1;;
  esac
done

case "$PART" in
  major|minor|patch) ;;
  *) echo "Unsupported part: $PART" >&2; exit 1;;
esac

PROMPT_ARGS=("python3" "scripts/prompt-version" "bump" "--prompts" "$PROMPTS" "--kind" "$KIND" "--lang" "$LANGS" "--part" "$PART")
if [[ "$DRY_RUN" -eq 1 ]]; then
  PROMPT_ARGS+=("--dry-run")
fi

echo "[prompt-release] bumping prompts (${PROMPT_ARGS[*]})"
"${PROMPT_ARGS[@]}"

echo "[prompt-release] running scripts/lint-prompts.py"
python3 scripts/lint-prompts.py

echo "[prompt-release] running pytest prompt suites"
python3 -m pytest tests/test_prompt_lint.py tests/test_prompt_diff.py tests/test_prompt_versioning.py

echo "[prompt-release] checking payload sync"
python3 tools/check_payload_sync.py --paths .claude,prompts,claude-presets,config,docs,templates,tools,workflow.md,CLAUDE.md,conventions.md,init-claude-workflow.sh,scripts/ci-lint.sh

echo "[prompt-release] running gate workflow tests"
python3 -m pytest tests/test_gate_workflow.py

echo "[prompt-release] completed"
