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

policy_skill="${ROOT_DIR}/skills/aidd-policy/SKILL.md"
require_rg "Status:" "$policy_skill"
require_rg "Work item key:" "$policy_skill"
require_rg "Artifacts updated:" "$policy_skill"
require_rg "Tests:" "$policy_skill"
require_rg "Blockers/Handoff:" "$policy_skill"
require_rg "Next actions:" "$policy_skill"
require_rg "AIDD:READ_LOG:" "$policy_skill"
require_rg "AIDD:ACTIONS_LOG:" "$policy_skill"

exit "$STATUS"
