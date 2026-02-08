#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATUS=0

log() { printf '[info] %s\n' "$*"; }
err() { printf '[error] %s\n' "$*" >&2; STATUS=1; }

require_contains() {
  local haystack="$1"
  local needle="$2"
  local label="$3"
  if [[ "$haystack" != *"$needle"* ]]; then
    err "$label: missing '$needle'"
  fi
}

cd "$ROOT_DIR"

log "checking actions validator supported versions"
actions_versions="$(python3 tools/actions-validate.sh --print-supported-versions 2>/dev/null || true)"
require_contains "$actions_versions" "aidd.actions.v0" "actions validator"
require_contains "$actions_versions" "aidd.actions.v1" "actions validator"

log "checking context-map validator supported versions"
map_versions="$(python3 tools/context-map-validate.sh --print-supported-versions 2>/dev/null || true)"
require_contains "$map_versions" "aidd.readmap.v1" "context-map validator"
require_contains "$map_versions" "aidd.writemap.v1" "context-map validator"

log "checking preflight-result validator supported versions"
preflight_versions="$(tools/preflight-result-validate.sh --print-supported-versions 2>/dev/null || true)"
require_contains "$preflight_versions" "aidd.stage_result.preflight.v1" "preflight-result validator"

log "validating skill contracts"
if ! python3 tools/skill-contract-validate.sh --all --quiet; then
  err "skill contracts validation failed"
fi

log "checking canonical schema registry"
if ! python3 - <<'PY'
from tools import aidd_schemas

required = {
    "aidd.actions.v0",
    "aidd.actions.v1",
    "aidd.skill_contract.v1",
    "aidd.readmap.v1",
    "aidd.writemap.v1",
    "aidd.stage_result.preflight.v1",
}
missing = sorted(name for name in required if name not in aidd_schemas.SCHEMA_FILES)
if missing:
    raise SystemExit(f"missing schema registrations: {', '.join(missing)}")
for name in sorted(required):
    path = aidd_schemas.schema_path(name)
    if not path.exists():
        raise SystemExit(f"missing schema file: {path}")
PY
then
  err "schema registry guard failed"
fi

exit "$STATUS"
