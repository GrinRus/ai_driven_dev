#!/usr/bin/env bash
#
# examples/apply-demo.sh
# Demonstrates applying init-claude-workflow.sh to the sample Gradle monorepo.
# Usage:
#   ./examples/apply-demo.sh [target-dir]
# If target-dir is omitted, a temporary directory will be created.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DEMO_SOURCE="$SCRIPT_DIR/gradle-demo"
INIT_SCRIPT="$REPO_ROOT/src/claude_workflow_cli/data/payload/aidd/init-claude-workflow.sh"

if [[ ! -f "$INIT_SCRIPT" ]]; then
  echo "[ERROR] init-claude-workflow.sh not found in payload: $INIT_SCRIPT" >&2
  exit 1
fi

TARGET_DIR="${1:-}"
CLEANUP=0
if [[ -z "$TARGET_DIR" ]]; then
  TARGET_DIR="$(mktemp -d "${TMPDIR:-/tmp}/claude-demo-XXXXXX")"
  CLEANUP=1
else
  mkdir -p "$TARGET_DIR"
fi

cleanup() {
  if [[ "$CLEANUP" -eq 1 ]]; then
    rm -rf "${TARGET_DIR:?}"
  fi
}
trap cleanup EXIT

copy_demo() {
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete "$DEMO_SOURCE/" "$TARGET_DIR/"
  else
    rm -rf "${TARGET_DIR:?}"/*
    cp -R "$DEMO_SOURCE/." "$TARGET_DIR/"
  fi
}

print_tree() {
  local title="$1"
  echo
  echo "=== $title ==="
  if command -v tree >/dev/null 2>&1; then
    (cd "$TARGET_DIR" && tree -L 2)
  else
    (cd "$TARGET_DIR" && find . -maxdepth 2 -print | sort)
  fi
}

copy_demo
print_tree "Structure before init"

pushd "$TARGET_DIR" >/dev/null

mkdir -p "$TARGET_DIR/aidd"

echo
echo ">>> Running init-claude-workflow.sh --enable-ci --force"
pushd "$TARGET_DIR/aidd" >/dev/null
bash "$INIT_SCRIPT" --enable-ci --force
popd >/dev/null

print_tree "Structure after init"

if [[ -x "./gradlew" ]]; then
  echo
  echo ">>> Running ./gradlew test (selective modules)"
  ./gradlew test >/dev/null || echo "[WARN] Gradle tests failed (check output above)"
else
  echo
  echo "[INFO] Gradle wrapper not bundled with demo. Install Gradle or run 'gradle wrapper' to execute tests."
fi

echo
echo "[NEXT STEPS]"
echo "  1. Используйте slug-hint при '/idea-new DEMO-1 demo-agent-first' и зафиксируйте все вводные в PRD."
echo "  2. Запустите 'claude-workflow research --ticket DEMO-1 --auto', чтобы собрать отчёты."
echo "  3. Продолжайте цикл '/plan-new → /tasks-new → /implement', опираясь на агент-first правила."

popd >/dev/null

if [[ "$CLEANUP" -eq 1 ]]; then
  echo
  echo "[INFO] Demo directory: $TARGET_DIR (removed after script exit)"
fi
