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

require_rg "n/a" "${ROOT_DIR}/commands/implement.md"
require_rg "n/a" "${ROOT_DIR}/commands/review.md"
require_rg "n/a" "${ROOT_DIR}/commands/qa.md"

require_rg "sync_drift_warn" "${ROOT_DIR}/commands/review.md"
require_rg "sync_drift_warn" "${ROOT_DIR}/commands/qa.md"

require_rg "stage_result" "${ROOT_DIR}/commands/review.md"
require_rg "review report" "${ROOT_DIR}/commands/review.md"
require_rg "review pack" "${ROOT_DIR}/commands/review.md"

require_rg "stage_result" "${ROOT_DIR}/commands/qa.md"
require_rg "qa report" "${ROOT_DIR}/commands/qa.md"

exit "$STATUS"
