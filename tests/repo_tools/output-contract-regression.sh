#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATUS=0

err() {
  printf '[error] %s\n' "$*" >&2
  STATUS=1
}

require_rg() {
  local pattern="$1"; shift
  local file="$1"; shift
  if ! rg -q "$pattern" "$file"; then
    err "missing pattern '$pattern' in $file"
  fi
}

core_skill="${ROOT_DIR}/skills/aidd-core/SKILL.md"
require_rg "Status:" "$core_skill"
require_rg "Work item key:" "$core_skill"
require_rg "Artifacts updated:" "$core_skill"
require_rg "Tests:" "$core_skill"
require_rg "Blockers/Handoff:" "$core_skill"
require_rg "Next actions:" "$core_skill"
require_rg "AIDD:READ_LOG:" "$core_skill"

exit "$STATUS"
