#!/usr/bin/env bash

# Shared helpers for stage wrappers (W92).

set -euo pipefail


aidd_bootstrap_plugin_root() {
  if [[ -n "${CLAUDE_PLUGIN_ROOT:-}" ]]; then
    return 0
  fi
  local here
  here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local plugin_root
  plugin_root="$(cd "${here}/../.." && pwd)"
  export CLAUDE_PLUGIN_ROOT="$plugin_root"
}


aidd_resolve_context() {
  local ticket="$1"
  local scope_key="$2"
  local work_item_key="$3"
  local stage="$4"
  local default_stage="$5"

  aidd_bootstrap_plugin_root

  local resolved
  resolved="$(python3 - <<'PY' "${ticket}" "${scope_key}" "${work_item_key}" "${stage}" "${default_stage}"
import json
import os
import shlex
import sys
from pathlib import Path

plugin_root = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", "")).expanduser().resolve()
if str(plugin_root) not in sys.path:
    sys.path.insert(0, str(plugin_root))

from tools import runtime

raw_ticket = sys.argv[1] or None
raw_scope = sys.argv[2] or None
raw_work_item = sys.argv[3] or None
raw_stage = sys.argv[4] or None
raw_default_stage = sys.argv[5] or None

_, root = runtime.require_workflow_root(Path.cwd())
resolved_ticket, _ = runtime.require_ticket(root, ticket=raw_ticket)
work_item = raw_work_item or runtime.read_active_work_item(root)
scope_key = raw_scope or runtime.resolve_scope_key(work_item, resolved_ticket)
if raw_stage:
    stage = raw_stage
elif raw_default_stage:
    stage = raw_default_stage
else:
    stage = runtime.read_active_stage(root)

values = {
    "AIDD_ROOT": str(root),
    "AIDD_TICKET": resolved_ticket,
    "AIDD_SCOPE_KEY": scope_key,
    "AIDD_WORK_ITEM_KEY": work_item or "",
    "AIDD_STAGE": stage or "",
}
for key, value in values.items():
    print(f"{key}={shlex.quote(value)}")
PY
)"
  eval "$resolved"
}


aidd_actions_paths() {
  local root="$1"
  local ticket="$2"
  local scope_key="$3"
  local stage="$4"
  local base="${root}/reports/actions/${ticket}/${scope_key}"
  export AIDD_ACTIONS_TEMPLATE="${base}/${stage}.actions.template.json"
  export AIDD_ACTIONS_PATH="${base}/${stage}.actions.json"
  export AIDD_APPLY_LOG="${base}/${stage}.apply.jsonl"
}


aidd_log_path() {
  local root="$1"
  local stage="$2"
  local ticket="$3"
  local scope_key="$4"
  local name="$5"
  local ts
  ts="$(date -u +"%Y%m%dT%H%M%SZ")"
  local dir="${root}/reports/logs/${stage}/${ticket}/${scope_key}"
  mkdir -p "$dir"
  printf '%s' "${dir}/wrapper.${name}.${ts}.log"
}


aidd_run_guarded() {
  local log_path="$1"; shift
  local stdout_tmp stderr_tmp
  stdout_tmp="$(mktemp)"
  stderr_tmp="$(mktemp)"
  local rc=0
  local errexit=0
  if [[ $- == *e* ]]; then
    errexit=1
  fi

  set +e
  (
    if ((errexit)); then
      set -e
    fi
    "$@"
  ) >"$stdout_tmp" 2>"$stderr_tmp"
  rc=$?
  if ((errexit)); then
    set -e
  fi

  if [[ -n "$log_path" ]]; then
    {
      printf '[stdout]\n'
      cat "$stdout_tmp"
      printf '\n[stderr]\n'
      cat "$stderr_tmp"
      printf '\n'
    } >>"$log_path"
  fi

  local stdout_lines stdout_bytes stderr_lines
  stdout_lines=$(wc -l <"$stdout_tmp" | tr -d ' ')
  stdout_bytes=$(wc -c <"$stdout_tmp" | tr -d ' ')
  stderr_lines=$(wc -l <"$stderr_tmp" | tr -d ' ')

  if (( stdout_lines > 200 || stdout_bytes > 51200 || stderr_lines > 50 )); then
    printf '[aidd] ERROR: output exceeded limits (stdout lines=%s bytes=%s, stderr lines=%s). See %s\n' \
      "$stdout_lines" "$stdout_bytes" "$stderr_lines" "$log_path" >&2
    rc=2
  else
    cat "$stdout_tmp"
    cat "$stderr_tmp" >&2
  fi

  rm -f "$stdout_tmp" "$stderr_tmp"
  return "$rc"
}
