#!/usr/bin/env bash
# Shared helpers for Claude workflow hooks.

_hook_python() {
  local mode="$1"
  shift
  HOOK_HELPER_MODE="$mode" PYTHONIOENCODING=utf-8 python3 - "$@" <<'PY'
import json
import os
import sys
from pathlib import Path

mode = os.environ.get("HOOK_HELPER_MODE")
if mode == "extract_path":
    payload = os.environ.get("HOOK_PAYLOAD") or ""
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        print("")
        raise SystemExit(0)
    print(data.get("tool_input", {}).get("file_path", ""))
elif mode == "config_get":
    cfg_path = Path(os.environ.get("HOOK_CFG_PATH", ""))
    key = os.environ.get("HOOK_CFG_KEY", "")
    default = os.environ.get("HOOK_CFG_DEFAULT", "")
    if not cfg_path.is_file():
        print(default)
        raise SystemExit(0)
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        print(default)
        raise SystemExit(0)
    value = data.get(key, default)
    if value is None:
        print(default)
    elif isinstance(value, bool):
        print("true" if value else "false")
    else:
        print(value)
elif mode == "read_slug":
    path = Path(os.environ.get("HOOK_SLUG_PATH", ""))
    if not path.is_file():
        raise SystemExit(0)
    try:
        print(path.read_text(encoding="utf-8").strip())
    except Exception:
        pass
elif mode == "read_ticket":
    ticket_path = Path(os.environ.get("HOOK_TICKET_PATH", ""))
    slug_path = Path(os.environ.get("HOOK_SLUG_PATH", ""))
    value = ""
    if ticket_path.is_file():
        try:
            value = ticket_path.read_text(encoding="utf-8").strip()
        except Exception:
            value = ""
    if not value and slug_path.is_file():
        try:
            value = slug_path.read_text(encoding="utf-8").strip()
        except Exception:
            value = ""
    if value:
        print(value)
else:
    raise SystemExit(f"Unsupported helper mode: {mode}")
PY
}

hook_payload_file_path() {
  local payload="$1"
  HOOK_PAYLOAD="$payload" _hook_python extract_path
}

_hook_config_get_raw() {
  local path="$1"
  local key="$2"
  local default="${3:-}"
  HOOK_CFG_PATH="$path" HOOK_CFG_KEY="$key" HOOK_CFG_DEFAULT="$default" \
    _hook_python config_get
}

hook_config_get_str() {
  _hook_config_get_raw "$@"
}

hook_config_get_bool() {
  local raw
  raw="$(_hook_config_get_raw "$@")"
  local norm
  norm="$(printf '%s' "$raw" | tr '[:upper:]' '[:lower:]')"
  case "$norm" in
    1|true|yes|on) printf '1\n' ;;
    0|false|no|off|"") printf '0\n' ;;
    *) printf '1\n' ;;
  esac
}

hook_read_slug() {
  local slug_path="$1"
  [[ -f "$slug_path" ]] || return 1
  HOOK_SLUG_PATH="$slug_path" _hook_python read_slug
}

hook_read_ticket() {
  local ticket_path="$1"
  local slug_path="${2:-}"
  local ticket_env=""
  local slug_env=""
  if [[ -n "$ticket_path" && -f "$ticket_path" ]]; then
    ticket_env="$ticket_path"
  fi
  if [[ -n "$slug_path" && -f "$slug_path" ]]; then
    slug_env="$slug_path"
  fi
  HOOK_TICKET_PATH="$ticket_env" HOOK_SLUG_PATH="$slug_env" _hook_python read_ticket
}
