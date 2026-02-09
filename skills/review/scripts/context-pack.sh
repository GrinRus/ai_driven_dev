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
FORWARD_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ticket)
      TICKET="$2"; FORWARD_ARGS+=("$1" "$2"); shift 2 ;;
    --scope-key)
      SCOPE_KEY="$2"; FORWARD_ARGS+=("$1" "$2"); shift 2 ;;
    --work-item-key)
      WORK_ITEM_KEY="$2"; FORWARD_ARGS+=("$1" "$2"); shift 2 ;;
    --stage)
      STAGE="$2"; FORWARD_ARGS+=("$1" "$2"); shift 2 ;;
    *)
      FORWARD_ARGS+=("$1"); shift ;;
  esac
done

aidd_resolve_context "$TICKET" "$SCOPE_KEY" "$WORK_ITEM_KEY" "$STAGE" "review"
LOG_PATH="$(aidd_log_path "$AIDD_ROOT" "$AIDD_STAGE" "$AIDD_TICKET" "$AIDD_SCOPE_KEY" "context-pack")"

run_tool() {
  aidd_run_python_module "review" "context-pack" "skills/review/runtime/context_pack.py" "${FORWARD_ARGS[@]}"
}

aidd_run_guarded "$LOG_PATH" run_tool
