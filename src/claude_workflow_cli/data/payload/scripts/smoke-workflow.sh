#!/usr/bin/env bash
# Smoke scenario for the Claude workflow bootstrap.
# This script is executed directly and via `claude-workflow smoke`.
# Creates a temporary project, runs init script, mimics the idea→plan→tasks cycle,
# and asserts that gate-workflow blocks/permits source edits as expected.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INIT_SCRIPT="${ROOT_DIR}/init-claude-workflow.sh"
TICKET="demo-checkout"
PAYLOAD='{"tool_input":{"file_path":"src/main/kotlin/App.kt"}}'
PYTHONPATH_CLI="${ROOT_DIR}/src"
if [[ -n "${PYTHONPATH:-}" ]]; then
  PYTHONPATH_CLI="${PYTHONPATH_CLI}:${PYTHONPATH}"
fi

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
log "initialise git repository"
git init -q
git config user.name "Smoke Bot"
git config user.email "smoke@example.com"

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

log "activate feature ticket"
mkdir -p docs
printf '%s' "$TICKET" >docs/.active_ticket
printf '%s' "$TICKET" >docs/.active_feature

log "expect block until PRD exists"
assert_gate_exit 2 "missing PRD"

log "apply preset feature-prd"
bash "$INIT_SCRIPT" --preset feature-prd --ticket "$TICKET" >/dev/null

log "mark analyst dialog ready"
python3 - "$TICKET" <<'PY'
from pathlib import Path
import sys

ticket = sys.argv[1]
path = Path("docs/prd") / f"{ticket}.prd.md"
text = path.read_text(encoding="utf-8")
if "## Диалог analyst" not in text:
    raise SystemExit("an analyst dialog block is expected in the PRD template")
if "Вопрос 1:" in text:
    text = text.replace(
        "Вопрос 1: `<Что нужно уточнить?>`",
        "Вопрос 1: Какие этапы checkout нужно покрыть в демо?",
        1,
    )
if "Ответ 1:" in text:
    text = text.replace(
        "Ответ 1: `<Ответ или TBD>`",
        "Ответ 1: Покрываем стандартный happy-path и ошибку оплаты.",
        1,
    )
if "Status: pending" in text:
    text = text.replace("Status: pending", "Status: READY", 1)
path.write_text(text, encoding="utf-8")
PY

log "analyst-check must pass"
python3 -m claude_workflow_cli.cli analyst-check --ticket "$TICKET" --target . >/dev/null

log "expect block until PRD review approved"
assert_gate_exit 2 "pending PRD review"

log "mark PRD review as approved"
python3 - "$TICKET" <<'PY'
from pathlib import Path
import sys

ticket = sys.argv[1]
path = Path("docs/prd") / f"{ticket}.prd.md"
content = path.read_text(encoding="utf-8")
if "## PRD Review" not in content:
    raise SystemExit("PRD Review section missing in smoke scenario")
if "Status: approved" not in content:
    content = content.replace("Status: pending", "Status: approved", 1)
path.write_text(content, encoding="utf-8")
PY

log "expect block until research report ready"
assert_gate_exit 2 "missing research report"

log "collect research artefacts"
python3 -m claude_workflow_cli.cli research --ticket "$TICKET" --target . >/dev/null

log "mark research summary as reviewed"
python3 - "$TICKET" <<'PY'
from pathlib import Path
import sys

ticket = sys.argv[1]
path = Path("docs/research") / f"{ticket}.md"
content = path.read_text(encoding="utf-8")
if "Status: reviewed" not in content:
    content = content.replace("Status: pending", "Status: reviewed", 1)
path.write_text(content, encoding="utf-8")
PY

log "expect block until plan exists"
assert_gate_exit 2 "missing plan"

log "apply preset feature-plan"
bash "$INIT_SCRIPT" --preset feature-plan --ticket "$TICKET" >/dev/null

log "expect block until tasks recorded"
assert_gate_exit 2 "missing tasklist items"

log "apply preset feature-impl"
bash "$INIT_SCRIPT" --preset feature-impl --ticket "$TICKET" >/dev/null
log "tasklist snapshot"
tail -n 10 "docs/tasklist/${TICKET}.md"

log "gate now allows source edits"
assert_gate_exit 0 "all artifacts ready"

log "commit baseline state"
git add .
git commit -qm "chore: smoke baseline"

log "modify source without updating tasklist"
cat <<'KT' >src/main/kotlin/App.kt
package demo

class App {
    fun run(): String = "updated"
}
KT

log "gate blocks when checkbox is missing"
assert_gate_exit 2 "missing progress checkbox"

log "progress CLI reports missing checkbox"
if progress_output="$(PYTHONPATH="$PYTHONPATH_CLI" python3 -m claude_workflow_cli.cli progress --target . --ticket "$TICKET" --source implement 2>&1)"; then
  printf '[smoke] expected progress CLI to fail but it succeeded:\n%s\n' "$progress_output" >&2
  exit 1
fi
echo "$progress_output" | grep -q "новых \`- \[x\]\`" || {
  printf '[smoke] unexpected progress CLI output:\n%s\n' "$progress_output" >&2
  exit 1
}

log "mark checkbox as completed in tasklist"
today="$(date +%Y-%m-%d)"
printf '\n- [x] Smoke iteration — %s • итерация 1\n' "$today" >> "docs/tasklist/${TICKET}.md"

log "progress CLI passes after checkbox update"
if ! progress_ok="$(PYTHONPATH="$PYTHONPATH_CLI" python3 -m claude_workflow_cli.cli progress --target . --ticket "$TICKET" --source implement --verbose 2>&1)"; then
  printf '[smoke] expected progress CLI to pass after checkbox update:\n%s\n' "$progress_ok" >&2
  exit 1
fi
assert_gate_exit 0 "progress checkbox added"

log "verify generated artifacts"
[[ -f "docs/prd/${TICKET}.prd.md" ]]
[[ -f "docs/plan/${TICKET}.md" ]]
grep -q "Claude Code" "docs/prd/${TICKET}.prd.md"

log "reviewer requests automated tests"
python3 -m claude_workflow_cli.cli reviewer-tests --ticket "$TICKET" --target . --status required >/dev/null
[[ -f "reports/reviewer/${TICKET}.json" ]] || {
  echo "[smoke] reviewer marker was not created" >&2
  exit 1
}

log "reviewer clears test requirement"
python3 -m claude_workflow_cli.cli reviewer-tests --ticket "$TICKET" --target . --status optional >/dev/null
grep -q "Status: approved" "docs/prd/${TICKET}.prd.md"
grep -q "Demo Checkout" "docs/tasklist/${TICKET}.md"

popd >/dev/null
log "smoke scenario passed"
