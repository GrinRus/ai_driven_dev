#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${CLAUDE_PROJECT_DIR:-${CLAUDE_PLUGIN_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}}"
if [[ "$(basename "$ROOT_DIR")" != "aidd" && -d "$ROOT_DIR/aidd/hooks" ]]; then
  echo "WARN: detected workspace root; using ${ROOT_DIR}/aidd as project root" >&2
  ROOT_DIR="$ROOT_DIR/aidd"
fi
if [[ ! -d "$ROOT_DIR/docs" ]]; then
  echo "BLOCK: aidd/docs not found at $ROOT_DIR/docs. Run init with '--target <workspace>' to install payload." >&2
  exit 2
fi
if [[ ! -d "$ROOT_DIR/docs" && -d "$ROOT_DIR/aidd/docs" ]]; then
  ROOT_DIR="$ROOT_DIR/aidd"
fi
# shellcheck source=hooks/lib.sh
source "${SCRIPT_DIR}/lib.sh"

payload="$(cat)"
file_path="$(hook_payload_file_path "$payload")"

ticket_source="$(hook_config_get_str config/gates.json feature_ticket_source docs/.active_ticket)"
slug_hint_source="$(hook_config_get_str config/gates.json feature_slug_hint_source docs/.active_feature)"
if [[ -z "$ticket_source" && -z "$slug_hint_source" ]]; then
  exit 0
fi
ticket="$(hook_read_ticket "$ticket_source" "$slug_hint_source" || true)"
[[ -n "$ticket" ]] || exit 0

branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '')"

prd_review_gate="$(resolve_script_path "scripts/prd_review_gate.py" || true)"
if ! review_msg="$(python3 "${prd_review_gate:-scripts/prd_review_gate.py}" --ticket "$ticket" --file-path "$file_path" --branch "$branch" --skip-on-prd-edit)"; then
  if [[ -n "$review_msg" ]]; then
    echo "$review_msg"
  else
    echo "BLOCK: PRD Review не готов → выполните /review-spec $ticket"
  fi
  exit 2
fi

exit 0
