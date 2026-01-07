#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=hooks/lib.sh
source "${SCRIPT_DIR}/lib.sh"
ROOT_DIR="$(hook_project_root)"
if [[ -z "$ROOT_DIR" ]]; then
  echo "[gate-prd-review] WARN: aidd root not found; skipping gate." >&2
  exit 0
fi
export ROOT_DIR
ROOT_PREFIX="$(hook_root_prefix "$ROOT_DIR")"

payload="$(cat)"
file_path="$(hook_payload_file_path "$payload")"
file_path="$(hook_normalize_path "$ROOT_DIR" "$file_path" "$ROOT_PREFIX")"

ticket_source="$(hook_config_get_str "$ROOT_DIR/config/gates.json" feature_ticket_source "$ROOT_DIR/docs/.active_ticket")"
slug_hint_source="$(hook_config_get_str "$ROOT_DIR/config/gates.json" feature_slug_hint_source "$ROOT_DIR/docs/.active_feature")"
if [[ -z "$ticket_source" && -z "$slug_hint_source" ]]; then
  exit 0
fi
if [[ -n "$ticket_source" && "$ticket_source" == aidd/* ]]; then
  ticket_source="$ROOT_DIR/${ticket_source#aidd/}"
fi
if [[ -n "$slug_hint_source" && "$slug_hint_source" == aidd/* ]]; then
  slug_hint_source="$ROOT_DIR/${slug_hint_source#aidd/}"
fi
if [[ -n "$ticket_source" && "$ticket_source" != /* ]]; then
  ticket_source="$ROOT_DIR/$ticket_source"
fi
if [[ -n "$slug_hint_source" && "$slug_hint_source" != /* ]]; then
  slug_hint_source="$ROOT_DIR/$slug_hint_source"
fi
ticket="$(hook_read_ticket "$ticket_source" "$slug_hint_source" || true)"
slug_hint="$(hook_read_slug "$slug_hint_source" || true)"
[[ -n "$ticket" ]] || exit 0

branch="$(git -C "$ROOT_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '')"

if ! review_msg="$(claude-workflow prd-review-gate --target "$ROOT_DIR" --ticket "$ticket" --slug-hint "$slug_hint" --file-path "$file_path" --branch "$branch" --skip-on-prd-edit)"; then
  if [[ -n "$review_msg" ]]; then
    echo "$review_msg"
  else
    echo "BLOCK: PRD Review не готов → выполните /review-spec $ticket"
  fi
  exit 2
fi

exit 0
