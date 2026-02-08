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
Usage: run.sh --ticket <ticket> --scope-key <scope> --work-item-key <work_item> --stage <stage> [--actions <path>]
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

aidd_resolve_context "$TICKET" "$SCOPE_KEY" "$WORK_ITEM_KEY" "$STAGE" "qa"
aidd_actions_paths "$AIDD_ROOT" "$AIDD_TICKET" "$AIDD_SCOPE_KEY" "$AIDD_STAGE"

ACTIONS_PROVIDED=0
if [[ -n "$ACTIONS_PATH" ]]; then
  ACTIONS_PROVIDED=1
  AIDD_ACTIONS_PATH="$ACTIONS_PATH"
fi

LOG_PATH="$(aidd_log_path "$AIDD_ROOT" "$AIDD_STAGE" "$AIDD_TICKET" "$AIDD_SCOPE_KEY" "run")"

main() {
  if [[ ! -f "$AIDD_ACTIONS_PATH" ]]; then
    if [[ -f "$AIDD_ACTIONS_TEMPLATE" ]]; then
      cp "$AIDD_ACTIONS_TEMPLATE" "$AIDD_ACTIONS_PATH"
    else
      mkdir -p "$(dirname "$AIDD_ACTIONS_PATH")"
      python3 - <<'PY' "$AIDD_ACTIONS_PATH" "$AIDD_STAGE" "$AIDD_TICKET" "$AIDD_SCOPE_KEY" "$AIDD_WORK_ITEM_KEY" >>"$LOG_PATH" 2>&1
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
stage = sys.argv[2]
ticket = sys.argv[3]
scope_key = sys.argv[4]
work_item_key = sys.argv[5]

payload = {
    "schema_version": "aidd.actions.v1",
    "stage": stage,
    "ticket": ticket,
    "scope_key": scope_key,
    "work_item_key": work_item_key,
    "allowed_action_types": [
        "tasklist_ops.set_iteration_done",
        "tasklist_ops.append_progress_log",
        "tasklist_ops.next3_recompute",
        "context_pack_ops.context_pack_update",
    ],
    "actions": [],
}
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
    fi
  fi

  "${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/actions-validate.sh" --actions "$AIDD_ACTIONS_PATH" >>"$LOG_PATH" 2>&1

  echo "log_path=aidd/${LOG_PATH#"${AIDD_ROOT}"/}"
  if [[ "$ACTIONS_PROVIDED" -eq 0 ]]; then
    echo "actions_path=aidd/${AIDD_ACTIONS_PATH#"${AIDD_ROOT}"/}"
  fi
  echo "summary=actions validated"
}

aidd_run_guarded "$LOG_PATH" main
