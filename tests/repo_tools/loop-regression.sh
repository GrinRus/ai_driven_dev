#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATUS=0

log() { printf '[info] %s\n' "$*"; }
err() { printf '[error] %s\n' "$*" >&2; STATUS=1; }
warn() { printf '[warn] %s\n' "$*" >&2; }

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
  if rg -n "preflight_prepare.py" "$file" >/dev/null 2>&1; then
    warn "internal preflight script mention detected in $file (telemetry-only policy)"
  fi
  require_rg "actions_apply.py" "$file"
  require_rg "Fill actions.json" "$file"
  require_rg "aidd-loop" "$file"
  require_rg "aidd-core" "$file"
done

log "checking loop-pack schema and active work item"
loop_pack_impl="aidd_runtime/loop_pack.py"
if [[ ! -f "${loop_pack_impl}" ]]; then
  loop_pack_impl="skills/aidd-loop/runtime/loop_pack.py"
fi
if rg -n "bootstrap_wrapper\\(" "${loop_pack_impl}" >/dev/null 2>&1; then
  if [[ -f "aidd_runtime/loop_pack_parts/core.py" ]]; then
    loop_pack_impl="aidd_runtime/loop_pack_parts/core.py"
  fi
fi
require_rg "aidd.loop_pack.v1" "${loop_pack_impl}"
require_rg "active.json" "${loop_pack_impl}"

log "checking loop-step/loop-run presence and docs"
if [[ ! -f "skills/aidd-loop/runtime/loop_step.py" ]]; then
  err "skills/aidd-loop/runtime/loop_step.py missing"
fi
if [[ ! -f "skills/aidd-loop/runtime/loop_run.py" ]]; then
  err "skills/aidd-loop/runtime/loop_run.py missing"
fi
require_rg "loop_step.py" "README.md"
require_rg "loop_run.py" "README.md"
require_rg "loop_step.py" "README.en.md"
require_rg "loop_run.py" "README.en.md"
require_rg "skills/aidd-loop/runtime/loop_step.py" "README.md"
require_rg "skills/aidd-loop/runtime/loop_run.py" "README.md"
require_rg "skills/aidd-loop/runtime/loop_step.py" "README.en.md"
require_rg "skills/aidd-loop/runtime/loop_run.py" "README.en.md"
exit "$STATUS"
