#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${CLAUDE_PROJECT_DIR:-${CLAUDE_PLUGIN_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}}"
if [[ "$(basename "$ROOT_DIR")" != "aidd" && ( -d "$ROOT_DIR/aidd/docs" || -d "$ROOT_DIR/aidd/hooks" ) ]]; then
  echo "[gate-qa] WARN: detected workspace root; using ${ROOT_DIR}/aidd as project root"
  ROOT_DIR="$ROOT_DIR/aidd"
fi
if [[ ! -d "$ROOT_DIR/docs" ]]; then
  echo "BLOCK: aidd/docs not found at $ROOT_DIR/docs. Run init with '--target <workspace>' to install payload." >&2
  exit 2
fi
# shellcheck source=hooks/lib.sh
source "${SCRIPT_DIR}/lib.sh"

EVENT_TYPE="gate-qa"
EVENT_STATUS=""
EVENT_REPORT=""
EVENT_SHOULD_LOG=0
EVENT_SOURCE="hook gate-qa"
trap 'if [[ "${EVENT_SHOULD_LOG:-0}" == "1" ]]; then hook_append_event "$ROOT_DIR" "$EVENT_TYPE" "$EVENT_STATUS" "" "$EVENT_REPORT" "$EVENT_SOURCE"; fi' EXIT

usage() {
  cat <<'EOF'
Usage: gate-qa.sh [--dry-run] [--only qa] [--payload <json>]

Environment:
  CLAUDE_SKIP_QA=1      — полностью пропустить гейт.
  CLAUDE_QA_DRY_RUN=1   — не проваливать выполнение при блокерах.
  CLAUDE_GATES_ONLY=qa  — запускать гейт только при явном перечислении.
  CLAUDE_QA_COMMAND     — переопределить команду запуска агента QA.
  QA_AGENT_DIFF_BASE    — ref/commit для сравнения diff (используется qa-agent через claude-workflow qa).
EOF
}

payload=""
if [[ -t 0 ]]; then
  payload=""
else
  payload="$(cat)"
fi

manual_dry=0
manual_only=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      manual_dry=1
      shift
      ;;
    --only)
      shift
      [[ $# -gt 0 ]] || { echo "[gate-qa] --only требует значение" >&2; exit 64; }
      manual_only="$1"
      shift
      ;;
    --payload)
      shift
      [[ $# -gt 0 ]] || { echo "[gate-qa] --payload требует JSON" >&2; exit 64; }
      payload="$1"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "[gate-qa] неизвестный аргумент: $1" >&2
      exit 64
      ;;
  esac
done

[[ "${CLAUDE_SKIP_QA:-0}" == "1" ]] && exit 0

should_run=1
filters=()
[[ -n "${CLAUDE_GATES_ONLY:-}" ]] && filters+=("${CLAUDE_GATES_ONLY}")
[[ -n "$manual_only" ]] && filters+=("$manual_only")

if ((${#filters[@]} > 0)); then
  should_run=0
  for raw in "${filters[@]}"; do
    [[ -z "$raw" ]] && continue
    IFS=', ' read -r -a parts <<< "$raw"
    for token in "${parts[@]}"; do
      [[ -z "$token" ]] && continue
      token_norm="$(printf '%s' "$token" | tr '[:upper:]' '[:lower:]')"
      if [[ "$token_norm" == "qa" ]]; then
        should_run=1
        break 2
      fi
    done
  done
fi

((should_run == 1)) || exit 0

dry_run=0
[[ "${CLAUDE_QA_DRY_RUN:-0}" == "1" ]] && dry_run=1
(( manual_dry == 1 )) && dry_run=1

cd "$ROOT_DIR"

if [[ "${CLAUDE_SKIP_STAGE_CHECKS:-0}" != "1" ]]; then
  active_stage="$(hook_resolve_stage "docs/.active_stage" || true)"
  if [[ "$active_stage" != "qa" ]]; then
    exit 0
  fi
fi

CONFIG_PATH="config/gates.json"
if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "[gate-qa] WARN: не найден $CONFIG_PATH — QA-гейт пропущен." >&2
  exit 0
fi

QA_CFG=()
while IFS= read -r line; do
  QA_CFG+=("$line")
done < <(
  python3 - "$CONFIG_PATH" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    data = json.loads(path.read_text(encoding="utf-8"))
except Exception as exc:  # pragma: no cover - config syntax errors
    print(f"PYERROR=failed to parse config/gates.json: {exc}")
    raise SystemExit(1)

qa = data.get("qa", {})
if isinstance(qa, bool):
    qa = {"enabled": qa}
elif qa is None:
    qa = {}
elif not isinstance(qa, dict):
    qa = {}

def norm_list(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item)]
    return []

SEP = "\x1f"

def emit(name, values):
    print(f"{name}=" + SEP.join(values))

enabled = bool(qa.get("enabled", True))
print(f"ENABLED={'1' if enabled else '0'}")
emit("BRANCHES", norm_list(qa.get("branches", [])))
emit("SKIP", norm_list(qa.get("skip_branches", [])))
emit("COMMAND", norm_list(qa.get("command", [])))
emit("BLOCK", [str(item).lower() for item in norm_list(qa.get('block_on', ('blocker', 'critical')))])
emit("WARN", [str(item).lower() for item in norm_list(qa.get('warn_on', ('major', 'minor')))])
emit("REQUIRES", norm_list(qa.get("requires", [])))
report = qa.get("report", "aidd/reports/qa/latest.json")
print(f"REPORT={report}")
timeout = int(qa.get("timeout", 600) or 0)
print(f"TIMEOUT={timeout}")
debounce = int(qa.get("debounce_minutes", 0) or 0)
print(f"DEBOUNCE={debounce}")
allow_missing = bool(qa.get("allow_missing_report", False))
print(f"ALLOW_MISSING={'1' if allow_missing else '0'}")
handoff = bool(qa.get("handoff", False))
print(f"HANDOFF={'1' if handoff else '0'}")
handoff_mode = qa.get("handoff_mode", qa.get("handoffMode", "warn"))
print(f"HANDOFF_MODE={handoff_mode}")
PY
) || {
  echo "[gate-qa] WARN: не удалось прочитать секцию qa из config/gates.json." >&2
  exit 0
}

qa_enabled=0
qa_timeout=600
qa_allow_missing=0
qa_report=""
qa_branches=()
qa_skip=()
qa_command=()
qa_block=()
qa_warn=()
qa_requires=()
qa_handoff=0
qa_handoff_mode=""
qa_debounce=0
list_sep=$'\x1f'

for line in "${QA_CFG[@]}"; do
  case "$line" in
    PYERROR=*)
      echo "[gate-qa] ${line#PYERROR=}" >&2
      exit 1
      ;;
    ENABLED=*)
      qa_enabled="${line#ENABLED=}"
      ;;
    REPORT=*)
      qa_report="${line#REPORT=}"
      ;;
    TIMEOUT=*)
      qa_timeout="${line#TIMEOUT=}"
      ;;
    DEBOUNCE=*)
      qa_debounce="${line#DEBOUNCE=}"
      ;;
    ALLOW_MISSING=*)
      qa_allow_missing="${line#ALLOW_MISSING=}"
      ;;
    HANDOFF=*)
      qa_handoff="${line#HANDOFF=}"
      ;;
    HANDOFF_MODE=*)
      qa_handoff_mode="${line#HANDOFF_MODE=}"
      ;;
    BRANCHES=*)
      raw="${line#BRANCHES=}"
      qa_branches=()
      if [[ -n "$raw" ]]; then
        IFS="$list_sep" read -r -a qa_branches <<< "$raw"
      fi
      ;;
    SKIP=*)
      raw="${line#SKIP=}"
      qa_skip=()
      if [[ -n "$raw" ]]; then
        IFS="$list_sep" read -r -a qa_skip <<< "$raw"
      fi
      ;;
    COMMAND=*)
      raw="${line#COMMAND=}"
      qa_command=()
      if [[ -n "$raw" ]]; then
        IFS="$list_sep" read -r -a qa_command <<< "$raw"
      fi
      ;;
    BLOCK=*)
      raw="${line#BLOCK=}"
      qa_block=()
      if [[ -n "$raw" ]]; then
        IFS="$list_sep" read -r -a qa_block <<< "$raw"
      fi
      ;;
    WARN=*)
      raw="${line#WARN=}"
      qa_warn=()
      if [[ -n "$raw" ]]; then
        IFS="$list_sep" read -r -a qa_warn <<< "$raw"
      fi
      ;;
    REQUIRES=*)
      raw="${line#REQUIRES=}"
      qa_requires=()
      if [[ -n "$raw" ]]; then
        IFS="$list_sep" read -r -a qa_requires <<< "$raw"
      fi
      ;;
  esac
done

[[ "$qa_enabled" == "1" ]] || exit 0

branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")"
[[ -n "$branch" ]] || branch="detached"

if ((${#qa_branches[@]} > 0)); then
  match=0
  # shellcheck disable=SC2053
  for pattern in "${qa_branches[@]}"; do
    [[ -z "$pattern" ]] && continue
    if [[ "$branch" == $pattern ]]; then
      match=1
      break
    fi
  done
  ((match == 1)) || exit 0
fi

if ((${#qa_skip[@]} > 0)); then
  # shellcheck disable=SC2053
  for pattern in "${qa_skip[@]}"; do
    [[ -z "$pattern" ]] && continue
    if [[ "$branch" == $pattern ]]; then
      exit 0
    fi
  done
fi

file_path="$(hook_payload_file_path "$payload")"
if [[ -n "$file_path" ]]; then
  case "$file_path" in
    docs/qa/*|reports/qa/*|aidd/docs/qa/*|aidd/reports/qa/*)
      : # всегда запускаем при обновлении QA артефактов
      ;;
    src/*|tests/*|docs/*|config/*|scripts/*)
      : # релевантные изменения
      ;;
    *)
      # не кодовая правка — можно пропустить
      exit 0
      ;;
  esac
fi

ticket_source="$(hook_config_get_str config/gates.json feature_ticket_source docs/.active_ticket)"
slug_hint_source="$(hook_config_get_str config/gates.json feature_slug_hint_source docs/.active_feature)"
ticket="$(hook_read_ticket "$ticket_source" "$slug_hint_source" || true)"
slug_hint="$(hook_read_slug "$slug_hint_source" || true)"

if ((${#qa_requires[@]} > 0)); then
  tests_mode="$(hook_config_get_str config/gates.json tests_required disabled)"
  for req in "${qa_requires[@]}"; do
    req_norm="$(printf '%s' "$req" | tr '[:upper:]' '[:lower:]')"
    case "$req_norm" in
      gate-tests)
        tests_mode_norm="$(printf '%s' "$tests_mode" | tr '[:upper:]' '[:lower:]')"
        if [[ "$tests_mode_norm" == "disabled" ]]; then
          echo "[gate-qa] WARN: qa.requires содержит gate-tests, но tests_required=disabled." >&2
        fi
        ;;
      gate-api-contract)
        if [[ "$(hook_config_get_bool config/gates.json api_contract)" != "1" ]]; then
          echo "[gate-qa] WARN: qa.requires содержит gate-api-contract, но гейт отключён." >&2
        fi
        ;;
    esac
  done
fi

if ((${#qa_command[@]} == 0)); then
  qa_command=("claude-workflow" "qa" "--gate")
fi

if [[ -n "${CLAUDE_QA_COMMAND:-}" ]]; then
  read -r -a override <<< "${CLAUDE_QA_COMMAND}"
  if ((${#override[@]} > 0)); then
    qa_command=("${override[@]}")
  fi
fi

replace_placeholders() {
  local raw="$1"
  local ticket_val="${ticket:-unknown}"
  local slug_val="${slug_hint:-$ticket_val}"
  local branch_val="${branch:-detached}"
  raw="${raw//\{ticket\}/$ticket_val}"
  raw="${raw//\{slug\}/$slug_val}"
  raw="${raw//\{branch\}/$branch_val}"
  printf '%s\n' "$raw"
}

cmd=()
for part in "${qa_command[@]}"; do
  [[ -z "$part" ]] && continue
  cmd+=("$(replace_placeholders "$part")")
done

# Команда должна вызывать установленный claude-workflow CLI.

if ((${#qa_block[@]} == 0)); then
  qa_block=("blocker" "critical")
fi
if ((${#qa_warn[@]} == 0)); then
  qa_warn=("major" "minor")
fi

block_arg="$(IFS=','; printf '%s' "${qa_block[*]}")"
warn_arg="$(IFS=','; printf '%s' "${qa_warn[*]}")"

has_gate=0
for part in "${cmd[@]}"; do
  if [[ "$part" == "--gate" ]]; then
    has_gate=1
    break
  fi
done

runner=("${cmd[@]}")
((has_gate == 1)) || runner+=("--gate")
runner+=("--block-on" "$block_arg" "--warn-on" "$warn_arg")
if [[ -n "$ticket" ]]; then
  runner+=("--ticket" "$ticket")
  if [[ -n "$slug_hint" && "$slug_hint" != "$ticket" ]]; then
    runner+=("--slug-hint" "$slug_hint")
  fi
fi
[[ -n "$branch" ]] && runner+=("--branch" "$branch")

report_path="$qa_report"
if [[ -n "$report_path" ]]; then
  report_path="$(replace_placeholders "$report_path")"
  report_path="${report_path#./}"
  if [[ "$report_path" == aidd/* && "$(basename "$ROOT_DIR")" == "aidd" ]]; then
    report_path="${report_path#aidd/}"
  fi
  runner+=("--report" "$report_path")
fi

debounce_minutes=0
stamp_path=""
if [[ "${CLAUDE_SKIP_QA_DEBOUNCE:-0}" != "1" ]]; then
  debounce_minutes="$qa_debounce"
  if [[ -n "${CLAUDE_QA_DEBOUNCE_MINUTES:-}" ]]; then
    debounce_minutes="${CLAUDE_QA_DEBOUNCE_MINUTES}"
  fi
  if [[ "$debounce_minutes" =~ ^[0-9]+$ ]] && (( debounce_minutes > 0 )); then
    now_ts="$(date +%s)"
    stamp_dir="aidd/reports/qa"
    if [[ -n "$report_path" ]]; then
      stamp_dir="$(dirname "$report_path")"
    fi
    stamp_dir="${stamp_dir:-aidd/reports/qa}"
    stamp_dir="${stamp_dir#./}"
    if [[ "$stamp_dir" == aidd/* && "$(basename "$ROOT_DIR")" == "aidd" ]]; then
      stamp_dir="${stamp_dir#aidd/}"
    fi
    stamp_path="${stamp_dir}/.gate-qa.${ticket:-unknown}.stamp"
    if [[ -f "$stamp_path" ]]; then
      last_ts="$(cat "$stamp_path" 2>/dev/null || true)"
      if [[ "$last_ts" =~ ^[0-9]+$ ]]; then
        delta=$(( now_ts - last_ts ))
        if (( delta < debounce_minutes * 60 )); then
          echo "[gate-qa] debounce: QA пропущен (${delta}s < ${debounce_minutes}m)." >&2
          exit 0
        fi
      fi
    fi
  fi
fi

((dry_run == 1)) && runner+=("--dry-run")

timeout_cmd=()
if [[ "$qa_timeout" =~ ^[0-9]+$ ]] && (( qa_timeout > 0 )); then
  if command -v timeout >/dev/null 2>&1; then
    timeout_cmd=(timeout "$qa_timeout")
  elif command -v gtimeout >/dev/null 2>&1; then
    timeout_cmd=(gtimeout "$qa_timeout")
  fi
fi

if [[ -n "$ticket" ]]; then
  if [[ -n "$slug_hint" && "$slug_hint" != "$ticket" ]]; then
    echo "[gate-qa] Запуск QA-агента (ветка: $branch, ticket: $ticket, slug hint: $slug_hint)" >&2
  else
    echo "[gate-qa] Запуск QA-агента (ветка: $branch, ticket: $ticket)" >&2
  fi
else
  echo "[gate-qa] Запуск QA-агента (ветка: $branch, ticket: n/a)" >&2
fi
((dry_run == 1)) && echo "[gate-qa] dry-run режим: блокеры не провалят команду." >&2

EVENT_SHOULD_LOG=1
EVENT_STATUS="fail"

set +e
if ((${#timeout_cmd[@]} > 0)); then
  "${timeout_cmd[@]}" "${runner[@]}"
else
  "${runner[@]}"
fi
status=$?
set -e

if [[ "$status" -eq 127 ]]; then
  echo "[gate-qa] ERROR: не удалось выполнить команду QA (${runner[0]})." >&2
fi

if [[ -n "$report_path" && ! -f "$report_path" ]]; then
  if [[ "$report_path" == *.json ]]; then
    pack_candidate="${report_path%.json}.pack.yaml"
    if [[ -f "$pack_candidate" ]]; then
      report_path="$pack_candidate"
    else
      pack_candidate="${report_path%.json}.pack.toon"
      [[ -f "$pack_candidate" ]] && report_path="$pack_candidate"
    fi
  fi
fi

if [[ -n "$report_path" && "$qa_allow_missing" == "0" ]]; then
  if [[ ! -f "$report_path" ]]; then
    echo "[gate-qa] ERROR: отчёт QA не создан: $report_path" >&2
    (( status == 0 )) && status=1
  fi
fi

if (( status == 0 )) && (( dry_run == 0 )) && [[ -n "$stamp_path" ]] && [[ "${CLAUDE_SKIP_QA_DEBOUNCE:-0}" != "1" ]]; then
  now_ts="$(date +%s)"
  stamp_dir="$(dirname "$stamp_path")"
  mkdir -p "$stamp_dir" 2>/dev/null || true
  printf '%s\n' "$now_ts" > "$stamp_path" 2>/dev/null || true
fi

if (( status == 0 )) && [[ "$qa_handoff" == "1" ]] && [[ "${CLAUDE_SKIP_QA_HANDOFF:-0}" != "1" ]]; then
  if [[ -n "$ticket" ]]; then
    echo "[gate-qa] handoff: формируем задачи из отчёта QA" >&2
    handoff_cmd=(tasks-derive --source qa --append --ticket "$ticket" --target "$ROOT_DIR")
    if [[ -n "$slug_hint" && "$slug_hint" != "$ticket" ]]; then
      handoff_cmd+=(--slug-hint "$slug_hint")
    fi
    if [[ -n "$report_path" ]]; then
      handoff_cmd+=(--report "$report_path")
    fi
    set +e
    run_cli_or_hint "${handoff_cmd[@]}"
    handoff_status=$?
    set -e
    if (( handoff_status != 0 )); then
      echo "[gate-qa] WARN: tasks-derive завершился с кодом $handoff_status (handoff пропущен)." >&2
    fi
  else
    echo "[gate-qa] WARN: ticket не определён — handoff пропущен." >&2
  fi
fi

handoff_mode="${qa_handoff_mode:-warn}"
if [[ -n "${CLAUDE_QA_HANDOFF_MODE:-}" ]]; then
  handoff_mode="$(printf '%s' "${CLAUDE_QA_HANDOFF_MODE}" | tr '[:upper:]' '[:lower:]')"
fi
case "$handoff_mode" in
  1|true|yes|on|block)
    handoff_mode="block"
    ;;
  0|false|no|off|skip|disabled)
    handoff_mode="off"
    ;;
  warn|warning)
    handoff_mode="warn"
    ;;
esac

if (( status == 0 )) && [[ "$qa_handoff" == "1" ]] && [[ "${CLAUDE_SKIP_QA_HANDOFF:-0}" != "1" ]] && [[ "$handoff_mode" != "off" ]]; then
  if [[ -n "$ticket" ]]; then
    handoff_check="$(python3 - "$ticket" "$handoff_mode" <<'PY'
import sys
from pathlib import Path

ticket = sys.argv[1]
mode = (sys.argv[2] or "warn").strip().lower()
tasklist_path = Path("docs/tasklist") / f"{ticket}.md"
prefix = "aidd/" if Path.cwd().name == "aidd" else ""
if not tasklist_path.exists():
    print(f"{mode.upper()}: tasklist не найден ({tasklist_path}).")
    raise SystemExit(0)

try:
    lines = tasklist_path.read_text(encoding="utf-8").splitlines()
except Exception:
    print(f"{mode.upper()}: не удалось прочитать {tasklist_path}.")
    raise SystemExit(0)

start = None
end = len(lines)
for idx, line in enumerate(lines):
    if line.strip().lower().startswith("## aidd:handoff_inbox"):
        start = idx
        break
if start is not None:
    for idx in range(start + 1, len(lines)):
        if lines[idx].strip().startswith("##"):
            end = idx
            break
    scan_text = "\n".join(lines[start:end]).lower()
else:
    scan_text = "\n".join(lines).lower()

markers = [
    f"{prefix}reports/qa/{ticket}".lower(),
    f"reports/qa/{ticket}".lower(),
]
if not any(marker in scan_text for marker in markers):
    hint = f"claude-workflow tasks-derive --source qa --append --ticket {ticket}"
    print(f"{mode.upper()}: handoff-задачи QA не найдены в tasklist. Запустите `{hint}`.")
PY
)"
    if [[ -n "$handoff_check" ]]; then
      if [[ "$handoff_mode" == "block" && "$dry_run" == "0" ]]; then
        echo "${handoff_check/BLOCK:/BLOCK:}" >&2
        status=2
      else
        echo "${handoff_check/BLOCK:/WARN:}" >&2
      fi
    fi
  fi
fi

if (( dry_run == 1 )); then
  EVENT_STATUS="skipped"
elif (( status == 0 )); then
  EVENT_STATUS="pass"
else
  EVENT_STATUS="fail"
fi
EVENT_REPORT="$report_path"

exit "$status"
