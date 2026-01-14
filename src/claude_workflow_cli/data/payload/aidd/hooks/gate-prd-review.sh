#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${CLAUDE_PROJECT_DIR:-${CLAUDE_PLUGIN_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}}"
if [[ "$(basename "$ROOT_DIR")" != "aidd" && ( -d "$ROOT_DIR/aidd/docs" || -d "$ROOT_DIR/aidd/hooks" ) ]]; then
  echo "[gate-prd-review] WARN: detected workspace root; using ${ROOT_DIR}/aidd as project root"
  ROOT_DIR="$ROOT_DIR/aidd"
fi
if [[ ! -d "$ROOT_DIR/docs" && -d "$ROOT_DIR/aidd/docs" ]]; then
  ROOT_DIR="$ROOT_DIR/aidd"
fi
if [[ ! -d "$ROOT_DIR/docs" ]]; then
  echo "BLOCK: aidd/docs not found at $ROOT_DIR/docs. Run init with '--target <workspace>' to install payload." >&2
  exit 2
fi
# shellcheck source=hooks/lib.sh
source "${SCRIPT_DIR}/lib.sh"

EVENT_TYPE="gate-prd-review"
EVENT_STATUS=""
EVENT_SHOULD_LOG=0
EVENT_SOURCE="hook gate-prd-review"
trap 'if [[ "${EVENT_SHOULD_LOG:-0}" == "1" ]]; then hook_append_event "$ROOT_DIR" "$EVENT_TYPE" "$EVENT_STATUS" "" "" "$EVENT_SOURCE"; fi' EXIT

payload="$(cat)"
file_path="$(hook_payload_file_path "$payload")"

ticket_source="$(hook_config_get_str config/gates.json feature_ticket_source docs/.active_ticket)"
slug_hint_source="$(hook_config_get_str config/gates.json feature_slug_hint_source docs/.active_feature)"
if [[ -z "$ticket_source" && -z "$slug_hint_source" ]]; then
  exit 0
fi
ticket="$(hook_read_ticket "$ticket_source" "$slug_hint_source" || true)"
slug_hint="$(hook_read_slug "$slug_hint_source" || true)"
[[ -n "$ticket" ]] || exit 0

EVENT_SHOULD_LOG=1
EVENT_STATUS="fail"

branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '')"

if ! review_msg="$(claude-workflow prd-review-gate --target "$ROOT_DIR" --ticket "$ticket" --slug-hint "$slug_hint" --file-path "$file_path" --branch "$branch" --skip-on-prd-edit)"; then
  if [[ -n "$review_msg" ]]; then
    echo "$review_msg"
  else
    echo "BLOCK: PRD Review не готов → выполните /review-spec $ticket"
  fi
  exit 2
fi

EVENT_STATUS="pass"
exit 0
