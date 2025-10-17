#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=.claude/hooks/lib.sh
source "${SCRIPT_DIR}/lib.sh"

payload="$(cat)"
file_path="$(hook_payload_file_path "$payload")"

slug_source="$(hook_config_get_str config/gates.json feature_slug_source docs/.active_feature)"
slug_source="${slug_source:-docs/.active_feature}"
[[ -f "$slug_source" ]] || exit 0
slug="$(hook_read_slug "$slug_source" || true)"
[[ -n "$slug" ]] || exit 0

branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '')"

if ! review_msg="$(python3 "$ROOT_DIR/scripts/prd_review_gate.py" --slug "$slug" --file-path "$file_path" --branch "$branch" --skip-on-prd-edit)"; then
  if [[ -n "$review_msg" ]]; then
    echo "$review_msg"
  else
    echo "BLOCK: PRD Review не готов → выполните /review-prd $slug"
  fi
  exit 2
fi

exit 0
