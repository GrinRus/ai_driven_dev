#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATUS=0

log() { printf '[info] %s\n' "$*"; }
err() { printf '[error] %s\n' "$*" >&2; STATUS=1; }

require_rg() {
  local pattern="$1"
  local file="$2"
  if ! rg -n "$pattern" "$file" >/dev/null 2>&1; then
    err "missing pattern '$pattern' in $file"
  fi
}

cd "$ROOT_DIR"

log "checking loop discipline markers in skills"
for stage in implement review qa; do
  file="skills/${stage}/SKILL.md"
  require_rg "preflight.sh" "$file"
  require_rg "postflight.sh" "$file"
  require_rg "Fill actions.json" "$file"
  require_rg "aidd-loop" "$file"
  require_rg "aidd-core" "$file"
done

log "checking loop-pack schema and active work item"
require_rg "aidd.loop_pack.v1" "skills/aidd-loop/runtime/loop_pack.py"
require_rg "active.json" "skills/aidd-loop/runtime/loop_pack.py"

log "checking loop-step/loop-run presence and docs"
if [[ ! -f "skills/aidd-loop/scripts/loop-step.sh" ]]; then
  err "skills/aidd-loop/scripts/loop-step.sh missing"
fi
if [[ ! -f "skills/aidd-loop/scripts/loop-run.sh" ]]; then
  err "skills/aidd-loop/scripts/loop-run.sh missing"
fi
require_rg "loop-step.sh" "README.md"
require_rg "loop-run.sh" "README.md"
require_rg "loop-step.sh" "README.en.md"
require_rg "loop-run.sh" "README.en.md"
require_rg "skills/aidd-loop/scripts/loop-step.sh" "README.md"
require_rg "skills/aidd-loop/scripts/loop-run.sh" "README.md"
require_rg "skills/aidd-loop/scripts/loop-step.sh" "README.en.md"
require_rg "skills/aidd-loop/scripts/loop-run.sh" "README.en.md"
exit "$STATUS"
