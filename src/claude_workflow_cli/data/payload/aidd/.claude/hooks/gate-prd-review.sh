#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
# shellcheck source=.claude/hooks/lib.sh
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

if ! review_msg="$(python3 "$ROOT_DIR/scripts/prd_review_gate.py" --ticket "$ticket" --file-path "$file_path" --branch "$branch" --skip-on-prd-edit)"; then
  if [[ -n "$review_msg" ]]; then
    echo "$review_msg"
  else
    echo "BLOCK: PRD Review не готов → выполните /review-prd $ticket"
  fi
  exit 2
fi

exit 0
