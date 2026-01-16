#!/usr/bin/env bash
# Shared helpers for Claude workflow hooks.

_hook_python() {
  local mode="$1"
  shift
  HOOK_HELPER_MODE="$mode" PYTHONIOENCODING=utf-8 python3 - "$@" <<'PY'
import datetime as dt
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
    tool_input = data.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    for key in ("file_path", "path", "filename", "file"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            print(value)
            raise SystemExit(0)
    for key in ("file_path", "path", "filename", "file"):
        value = data.get(key)
        if isinstance(value, str) and value:
            print(value)
            raise SystemExit(0)
    print("")
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
elif mode == "append_event":
    root_raw = os.environ.get("HOOK_EVENT_ROOT", "")
    ticket = os.environ.get("HOOK_EVENT_TICKET", "").strip()
    if not root_raw or not ticket:
        raise SystemExit(0)
    root = Path(root_raw)
    if not root.exists():
        raise SystemExit(0)
    slug_hint = os.environ.get("HOOK_EVENT_SLUG", "").strip() or None
    event_type = os.environ.get("HOOK_EVENT_TYPE", "").strip()
    if not event_type:
        raise SystemExit(0)
    status = os.environ.get("HOOK_EVENT_STATUS", "").strip()
    details_raw = os.environ.get("HOOK_EVENT_DETAILS", "").strip()
    details = None
    if details_raw:
        try:
            details = json.loads(details_raw)
        except json.JSONDecodeError:
            details = {"summary": details_raw}
    report = os.environ.get("HOOK_EVENT_REPORT", "").strip()
    source = os.environ.get("HOOK_EVENT_SOURCE", "").strip()
    payload = {
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "ticket": ticket,
        "slug_hint": slug_hint,
        "type": event_type,
    }
    if status:
        payload["status"] = status
    if details:
        payload["details"] = details
    if report:
        payload["report"] = report
    if source:
        payload["source"] = source
    path = root / "reports" / "events" / f"{ticket}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
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

hook_read_stage() {
  local stage_path="${1:-docs/.active_stage}"
  [[ -f "$stage_path" ]] || return 1
  local value
  value="$(tr -d '\r' <"$stage_path" | tr -d '\n')"
  value="$(printf '%s' "$value" | tr '[:upper:]' '[:lower:]')"
  if [[ -n "$value" ]]; then
    printf '%s\n' "$value"
    return 0
  fi
  return 1
}

hook_resolve_stage() {
  local override="${CLAUDE_ACTIVE_STAGE:-}"
  if [[ -n "$override" ]]; then
    printf '%s\n' "$(printf '%s' "$override" | tr '[:upper:]' '[:lower:]')"
    return 0
  fi
  hook_read_stage "${1:-docs/.active_stage}"
}

run_cli_or_hint() {
  if command -v claude-workflow >/dev/null 2>&1; then
    claude-workflow "$@"
    return $?
  fi
  echo "[claude-workflow] CLI 'claude-workflow' не найден. Установите его командой" >&2
  echo "  uv tool install claude-workflow-cli --from git+https://github.com/GrinRus/ai_driven_dev.git" >&2
  echo "или" >&2
  echo "  pipx install git+https://github.com/GrinRus/ai_driven_dev.git" >&2
  return 127
}

hook_append_event() {
  local root="$1"
  local event_type="$2"
  local status="${3:-}"
  local details="${4:-}"
  local report="${5:-}"
  local source="${6:-}"
  [[ -n "$root" ]] || return 0
  local ticket
  local slug
  ticket="$(hook_read_ticket "$root/docs/.active_ticket" "$root/docs/.active_feature" || true)"
  [[ -n "$ticket" ]] || return 0
  slug="$(hook_read_slug "$root/docs/.active_feature" || true)"
  HOOK_EVENT_ROOT="$root" \
    HOOK_EVENT_TICKET="$ticket" \
    HOOK_EVENT_SLUG="$slug" \
    HOOK_EVENT_TYPE="$event_type" \
    HOOK_EVENT_STATUS="$status" \
    HOOK_EVENT_DETAILS="$details" \
    HOOK_EVENT_REPORT="$report" \
    HOOK_EVENT_SOURCE="$source" \
    _hook_python append_event
}

ensure_template() {
  local src="$1"
  local dest="$2"
  if [[ -z "$src" || -z "$dest" ]]; then
    return 1
  fi
  if [[ -f "$dest" ]]; then
    return 0
  fi
  local src_path=""
  if [[ -n "${ROOT_DIR:-}" && -f "$ROOT_DIR/$src" ]]; then
    src_path="$ROOT_DIR/$src"
  fi
  mkdir -p "$(dirname "$dest")"
  if [[ -n "$src_path" ]]; then
    cp "$src_path" "$dest"
    return 0
  fi
  # fallback: create minimal stub
  cat >"$dest" <<'EOF'
# Research

Status: pending

## Summary

## Findings
- TBD

## Next steps
- TBD
EOF
  return 0
}

hook_prefix_lines() {
  local prefix="$1"
  if [[ -z "$prefix" ]]; then
    cat
    return 0
  fi
  local line
  while IFS= read -r line; do
    printf '%s %s\n' "$prefix" "$line"
  done
}
