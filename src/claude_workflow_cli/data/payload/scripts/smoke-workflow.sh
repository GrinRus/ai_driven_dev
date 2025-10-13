#!/usr/bin/env bash
# Smoke scenario for the Claude workflow bootstrap.
# This script is executed directly and via `claude-workflow smoke`.
# Creates a temporary project, runs init script, mimics the idea→plan→tasks cycle,
# and asserts that gate-workflow blocks/permits source edits as expected.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INIT_SCRIPT="${ROOT_DIR}/init-claude-workflow.sh"
SLUG="demo-checkout"
PAYLOAD='{"tool_input":{"file_path":"src/main/kotlin/App.kt"}}'

[[ -x "$INIT_SCRIPT" ]] || {
  echo "[smoke] missing init script at $INIT_SCRIPT" >&2
  exit 1
}

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/claude-workflow-smoke.XXXXXX")"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

log() {
  printf '[smoke] %s\n' "$*"
}

assert_gate_exit() {
  local expected="$1"
  local note="$2"
  local output rc
  set +e
  output="$(CLAUDE_PROJECT_DIR="$PWD" ./.claude/hooks/gate-workflow.sh <<<"$PAYLOAD" 2>&1)"
  rc=$?
  set -e
  if [[ "$rc" -ne "$expected" ]]; then
    printf '[smoke] gate-workflow mismatch (%s): expected %s, got %s\n' "$note" "$expected" "$rc" >&2
    printf '[smoke] gate output:\n%s\n' "$output" >&2
    exit 1
  fi
  log "gate-workflow -> ${rc} (${note})"
}

log "working directory: $TMP_DIR"
pushd "$TMP_DIR" >/dev/null

log "bootstrap workflow scaffolding"
bash "$INIT_SCRIPT" --force >/dev/null

log "create demo source file"
mkdir -p src/main/kotlin
cat <<'KT' >src/main/kotlin/App.kt
package demo

class App {
    fun run(): String = "ok"
}
KT

log "gate allows edits when feature inactive"
assert_gate_exit 0 "no active feature"

log "activate feature slug"
mkdir -p docs
printf '%s' "$SLUG" >docs/.active_feature

log "expect block until PRD exists"
assert_gate_exit 2 "missing PRD"

log "apply preset feature-prd"
bash "$INIT_SCRIPT" --preset feature-prd --feature "$SLUG" >/dev/null

log "expect block until plan exists"
assert_gate_exit 2 "missing plan"

log "apply preset feature-plan"
bash "$INIT_SCRIPT" --preset feature-plan --feature "$SLUG" >/dev/null

log "expect block until tasks recorded"
assert_gate_exit 2 "missing tasklist items"

log "apply preset feature-impl"
bash "$INIT_SCRIPT" --preset feature-impl --feature "$SLUG" >/dev/null
log "tasklist snapshot"
tail -n 10 tasklist.md

log "gate now allows source edits"
assert_gate_exit 0 "all artifacts ready"

log "verify generated artifacts"
[[ -f "docs/prd/${SLUG}.prd.md" ]]
[[ -f "docs/plan/${SLUG}.md" ]]
grep -q "Claude Code" "docs/prd/${SLUG}.prd.md"
grep -q "Demo Checkout" tasklist.md

popd >/dev/null
log "smoke scenario passed"
