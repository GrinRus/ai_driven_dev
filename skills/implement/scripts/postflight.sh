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
RESULT=""
VERDICT=""

usage() {
  cat <<'EOF'
Usage: postflight.sh --ticket <ticket> --scope-key <scope> --work-item-key <work_item> --stage <stage> [--actions <path>] [--result <continue|done|blocked>] [--verdict <SHIP|REVISE|BLOCKED>]
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
    --result)
      RESULT="$2"; shift 2 ;;
    --verdict)
      VERDICT="$2"; shift 2 ;;
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

LOG_PATH="$(aidd_log_path "$AIDD_ROOT" "$AIDD_STAGE" "$AIDD_TICKET" "$AIDD_SCOPE_KEY" "postflight")"

main() {
  if [[ ! -f "$AIDD_ACTIONS_PATH" ]]; then
    echo "actions file missing: $AIDD_ACTIONS_PATH" >&2
    return 2
  fi

  {
    "${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/actions-apply.sh" \
      --actions "$AIDD_ACTIONS_PATH" \
      --apply-log "$AIDD_APPLY_LOG"

    "${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/diff-boundary-check.sh" --ticket "$AIDD_TICKET"
    "${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/progress.sh" --ticket "$AIDD_TICKET" --source implement

    local stage_result
    stage_result="${RESULT:-continue}"
    local stage_result_cmd=("${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/stage-result.sh" --ticket "$AIDD_TICKET" --stage "$AIDD_STAGE" --result "$stage_result" --scope-key "$AIDD_SCOPE_KEY")
    if [[ -n "$AIDD_WORK_ITEM_KEY" ]]; then
      stage_result_cmd+=(--work-item-key "$AIDD_WORK_ITEM_KEY")
    fi
    if [[ -n "$VERDICT" ]]; then
      stage_result_cmd+=(--verdict "$VERDICT")
    fi
    "${stage_result_cmd[@]}"

    "${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/status-summary.sh" --ticket "$AIDD_TICKET" --stage "$AIDD_STAGE" --scope-key "$AIDD_SCOPE_KEY"
  } >>"$LOG_PATH" 2>&1

  echo "log_path=aidd/${LOG_PATH#"${AIDD_ROOT}"/}"
  echo "apply_log=aidd/${AIDD_APPLY_LOG#"${AIDD_ROOT}"/}"
  if [[ "$ACTIONS_PROVIDED" -eq 0 ]]; then
    echo "actions_path=aidd/${AIDD_ACTIONS_PATH#"${AIDD_ROOT}"/}"
  fi
  echo "summary=postflight ok"
}

aidd_run_guarded "$LOG_PATH" main
