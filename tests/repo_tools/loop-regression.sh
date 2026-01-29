#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATUS=0
TICKET_LITERAL="\$1"
TICKET_REGEX="\\\$1"

log() { printf '[info] %s\n' "$*"; }
err() { printf '[error] %s\n' "$*" >&2; STATUS=1; }

require_rg() {
  local pattern="$1"
  local file="$2"
  if ! rg -n "$pattern" "$file" >/dev/null 2>&1; then
    err "missing pattern '$pattern' in $file"
  fi
}

check_order() {
  local file="$1"
  local first="$2"
  local second="$3"
  if ! python3 - "$file" "$first" "$second" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
first = sys.argv[2]
second = sys.argv[3]
lines = path.read_text(encoding="utf-8").splitlines()
first_idx = next((i for i, line in enumerate(lines) if first in line), None)
second_idx = next((i for i, line in enumerate(lines) if second in line), None)
if first_idx is None or second_idx is None or first_idx >= second_idx:
    raise SystemExit(1)
PY
  then
    err "order check failed in $file: '$first' should appear before '$second'"
  fi
}

cd "$ROOT_DIR"

log "checking loop-pack wiring in commands"
require_rg "loop-pack.sh --ticket ${TICKET_REGEX} --stage implement" "commands/implement.md"
require_rg "aidd/reports/loops/${TICKET_REGEX}/<work_item_key>\\.loop\\.pack\\.md" "commands/implement.md"
require_rg "diff-boundary-check.sh --ticket ${TICKET_REGEX}" "commands/implement.md"
require_rg "OUT_OF_SCOPE" "commands/implement.md"
require_rg "loop-pack.sh --ticket ${TICKET_REGEX} --stage review" "commands/review.md"
require_rg "review-pack.sh --ticket ${TICKET_REGEX}" "commands/review.md"
require_rg "diff-boundary-check.sh --ticket ${TICKET_REGEX}" "commands/review.md"
require_rg "OUT_OF_SCOPE" "commands/review.md"
check_order "commands/review.md" "loop-pack.sh --ticket ${TICKET_LITERAL} --stage review" "Use the feature-dev-aidd:reviewer subagent"

log "checking loop protocol anchors"
require_rg "Loop discipline" "templates/aidd/docs/anchors/implement.md"
require_rg "Loop discipline" "templates/aidd/docs/anchors/review.md"

log "checking loop-pack schema and active work item"
require_rg "aidd.loop_pack.v1" "tools/loop_pack.py"
require_rg ".active_work_item" "tools/loop_pack.py"

log "checking loop-step/loop-run presence and docs"
if [[ ! -f "tools/loop-step.sh" ]]; then
  err "tools/loop-step.sh missing"
fi
if [[ ! -f "tools/loop-run.sh" ]]; then
  err "tools/loop-run.sh missing"
fi
require_rg "loop-step.sh" "README.md"
require_rg "loop-run.sh" "README.md"
require_rg "loop-step.sh" "README.en.md"
require_rg "loop-run.sh" "README.en.md"
require_rg "loop-step.sh" "templates/aidd/docs/loops/README.md"
require_rg "loop-run.sh" "templates/aidd/docs/loops/README.md"

exit "$STATUS"
