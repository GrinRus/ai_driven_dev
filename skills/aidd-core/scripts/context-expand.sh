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
PATH_REF=""
REASON_CODE=""
REASON=""
EXPAND_WRITE=0
NO_REGENERATE_PACK=0

usage() {
  cat <<'EOU'
Usage: context-expand.sh --path <path[#AIDD:...|@handoff:...]> --reason-code <code> --reason <text> [--expand-write] [--no-regenerate-pack] [--ticket <ticket>] [--scope-key <scope>] [--work-item-key <work_item>] [--stage <stage>]
EOU
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
    --path)
      PATH_REF="$2"; shift 2 ;;
    --reason-code)
      REASON_CODE="$2"; shift 2 ;;
    --reason)
      REASON="$2"; shift 2 ;;
    --expand-write)
      EXPAND_WRITE=1; shift ;;
    --no-regenerate-pack)
      NO_REGENERATE_PACK=1; shift ;;
    --help|-h)
      usage; exit 0 ;;
    *)
      shift ;;
  esac
done

if [[ -z "$PATH_REF" || -z "$REASON_CODE" || -z "$REASON" ]]; then
  usage >&2
  exit 2
fi

aidd_resolve_context "$TICKET" "$SCOPE_KEY" "$WORK_ITEM_KEY" "$STAGE" ""
if [[ -z "${AIDD_STAGE:-}" ]]; then
  AIDD_STAGE="implement"
fi
aidd_actions_paths "$AIDD_ROOT" "$AIDD_TICKET" "$AIDD_SCOPE_KEY" "$AIDD_STAGE"

LOG_PATH="$(aidd_log_path "$AIDD_ROOT" "$AIDD_STAGE" "$AIDD_TICKET" "$AIDD_SCOPE_KEY" "context-expand")"

main() {
  export PYTHONPATH="${CLAUDE_PLUGIN_ROOT}:${PYTHONPATH:-}"
  local cmd=(
    python3
    "${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/runtime/context_expand.py"
    --ticket "$AIDD_TICKET"
    --scope-key "$AIDD_SCOPE_KEY"
    --work-item-key "$AIDD_WORK_ITEM_KEY"
    --stage "$AIDD_STAGE"
    --path "$PATH_REF"
    --reason-code "$REASON_CODE"
    --reason "$REASON"
  )

  if [[ "$EXPAND_WRITE" -eq 1 ]]; then
    cmd+=(--expand-write)
  fi
  if [[ "$NO_REGENERATE_PACK" -eq 1 ]]; then
    cmd+=(--no-regenerate-pack)
  fi

  local expand_out
  if ! expand_out="$("${cmd[@]}" 2>&1)"; then
    printf '%s\n' "$expand_out" >>"$LOG_PATH"
    printf '%s\n' "$expand_out"
    return 2
  fi
  printf '%s\n' "$expand_out" >>"$LOG_PATH"
  printf '%s\n' "$expand_out"

  echo "log_path=aidd/${LOG_PATH#"${AIDD_ROOT}"/}"
}

aidd_run_guarded "$LOG_PATH" main
