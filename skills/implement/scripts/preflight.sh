#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
export CLAUDE_PLUGIN_ROOT="$PLUGIN_ROOT"

# shellcheck source=/dev/null
source "${CLAUDE_PLUGIN_ROOT}/skills/aidd-reference/wrapper_lib.sh"

TICKET=""
SCOPE_KEY=""
WORK_ITEM_KEY=""
STAGE=""
ACTIONS_PATH=""

usage() {
  cat <<'EOF'
Usage: preflight.sh --ticket <ticket> --scope-key <scope> --work-item-key <work_item> --stage <stage> [--actions <path>]
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ticket)
      TICKET="$2"; shift 2 ;;
    --scope-key)
      SCOPE_KEY="$2"; shift 2 ;;
    --work-item-key)
      WORK_ITEM_KEY="$2"; shift 2 ;;
    --stage)
      STAGE="$2"; shift 2 ;;
    --actions)
      ACTIONS_PATH="$2"; shift 2 ;;
    --help|-h)
      usage; exit 0 ;;
    *)
      shift ;;
  esac
done

aidd_resolve_context "$TICKET" "$SCOPE_KEY" "$WORK_ITEM_KEY" "$STAGE" "implement"
aidd_actions_paths "$AIDD_ROOT" "$AIDD_TICKET" "$AIDD_SCOPE_KEY" "$AIDD_STAGE"

ACTIONS_PROVIDED=0
if [[ -n "$ACTIONS_PATH" ]]; then
  ACTIONS_PROVIDED=1
  AIDD_ACTIONS_PATH="$ACTIONS_PATH"
fi

LOG_PATH="$(aidd_log_path "$AIDD_ROOT" "$AIDD_STAGE" "$AIDD_TICKET" "$AIDD_SCOPE_KEY" "preflight")"

main() {
  mkdir -p "$(dirname "$AIDD_ACTIONS_TEMPLATE")"

  {
    "${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/set-active-feature.sh" "$AIDD_TICKET"
    "${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/set-active-stage.sh" "$AIDD_STAGE"
    "${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/prd-check.sh" --ticket "$AIDD_TICKET"
  } >>"$LOG_PATH" 2>&1

  local preflight_out
  if ! preflight_out="$("${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/scripts/preflight-prepare.sh" \
    --ticket "$AIDD_TICKET" \
    --scope-key "$AIDD_SCOPE_KEY" \
    --work-item-key "$AIDD_WORK_ITEM_KEY" \
    --stage "$AIDD_STAGE" \
    --actions-template "$AIDD_ACTIONS_TEMPLATE" \
    --readmap-json "$AIDD_READMAP_JSON" \
    --readmap-md "$AIDD_READMAP_MD" \
    --writemap-json "$AIDD_WRITEMAP_JSON" \
    --writemap-md "$AIDD_WRITEMAP_MD" \
    --result "$AIDD_PREFLIGHT_RESULT" 2>&1)"; then
    printf '%s\n' "$preflight_out" >>"$LOG_PATH"
    printf '%s\n' "$preflight_out" >&2
    return 2
  fi
  printf '%s\n' "$preflight_out" >>"$LOG_PATH"

  {
    "${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/context-map-validate.sh" --map "$AIDD_READMAP_JSON"
    "${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/context-map-validate.sh" --map "$AIDD_WRITEMAP_JSON"
    "${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/actions-validate.sh" --actions "$AIDD_ACTIONS_TEMPLATE"
    "${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/scripts/preflight-result-validate.sh" --result "$AIDD_PREFLIGHT_RESULT"
  } >>"$LOG_PATH" 2>&1

  aidd_write_fallback_preflight_artifacts

  echo "log_path=aidd/${LOG_PATH#"${AIDD_ROOT}"/}"
  echo "template_path=aidd/${AIDD_ACTIONS_TEMPLATE#"${AIDD_ROOT}"/}"
  echo "readmap_path=aidd/${AIDD_READMAP_JSON#"${AIDD_ROOT}"/}"
  echo "writemap_path=aidd/${AIDD_WRITEMAP_JSON#"${AIDD_ROOT}"/}"
  echo "preflight_result=aidd/${AIDD_PREFLIGHT_RESULT#"${AIDD_ROOT}"/}"
  if [[ "$ACTIONS_PROVIDED" -eq 0 ]]; then
    echo "actions_path=aidd/${AIDD_ACTIONS_PATH#"${AIDD_ROOT}"/}"
  fi
  echo "summary=preflight ok"
}

aidd_run_guarded "$LOG_PATH" main
