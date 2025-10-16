#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=.claude/hooks/lib.sh
source "${SCRIPT_DIR}/lib.sh"

usage() {
  cat <<'EOF'
Usage: gate-qa.sh [--dry-run] [--only qa] [--payload <json>]

Environment:
  CLAUDE_SKIP_QA=1      — полностью пропустить гейт.
  CLAUDE_QA_DRY_RUN=1   — не проваливать выполнение при блокерах.
  CLAUDE_GATES_ONLY=qa  — запускать гейт только при явном перечислении.
  CLAUDE_QA_COMMAND     — переопределить команду запуска агента QA.
  QA_AGENT_DIFF_BASE    — ref/commit для сравнения diff (используется qa-agent.py).
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
      if [[ "${token,,}" == "qa" ]]; then
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

CONFIG_PATH="config/gates.json"
if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "[gate-qa] WARN: не найден $CONFIG_PATH — QA-гейт пропущен." >&2
  exit 0
fi

mapfile -t QA_CFG < <(
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

def emit(name, values):
    print(f"{name}=" + "\0".join(values))

enabled = bool(qa.get("enabled", True))
print(f"ENABLED={'1' if enabled else '0'}")
emit("BRANCHES", norm_list(qa.get("branches", [])))
emit("SKIP", norm_list(qa.get("skip_branches", [])))
emit("COMMAND", norm_list(qa.get("command", [])))
emit("BLOCK", [str(item).lower() for item in norm_list(qa.get('block_on', ('blocker', 'critical')))])
emit("WARN", [str(item).lower() for item in norm_list(qa.get('warn_on', ('major', 'minor')))])
emit("REQUIRES", norm_list(qa.get("requires", [])))
report = qa.get("report", "reports/qa/latest.json")
print(f"REPORT={report}")
timeout = int(qa.get("timeout", 600) or 0)
print(f"TIMEOUT={timeout}")
allow_missing = bool(qa.get("allow_missing_report", False))
print(f"ALLOW_MISSING={'1' if allow_missing else '0'}")
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
    ALLOW_MISSING=*)
      qa_allow_missing="${line#ALLOW_MISSING=}"
      ;;
    BRANCHES=*)
      raw="${line#BRANCHES=}"
      qa_branches=()
      if [[ -n "$raw" ]]; then
        IFS=$'\0' read -r -a qa_branches <<< "$raw"
      fi
      ;;
    SKIP=*)
      raw="${line#SKIP=}"
      qa_skip=()
      if [[ -n "$raw" ]]; then
        IFS=$'\0' read -r -a qa_skip <<< "$raw"
      fi
      ;;
    COMMAND=*)
      raw="${line#COMMAND=}"
      qa_command=()
      if [[ -n "$raw" ]]; then
        IFS=$'\0' read -r -a qa_command <<< "$raw"
      fi
      ;;
    BLOCK=*)
      raw="${line#BLOCK=}"
      qa_block=()
      if [[ -n "$raw" ]]; then
        IFS=$'\0' read -r -a qa_block <<< "$raw"
      fi
      ;;
    WARN=*)
      raw="${line#WARN=}"
      qa_warn=()
      if [[ -n "$raw" ]]; then
        IFS=$'\0' read -r -a qa_warn <<< "$raw"
      fi
      ;;
    REQUIRES=*)
      raw="${line#REQUIRES=}"
      qa_requires=()
      if [[ -n "$raw" ]]; then
        IFS=$'\0' read -r -a qa_requires <<< "$raw"
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
    docs/qa/*|reports/qa/*)
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

slug_source="$(hook_config_get_str config/gates.json feature_slug_source docs/.active_feature)"
slug=""
if [[ -n "$slug_source" && -f "$slug_source" ]]; then
  slug="$(hook_read_slug "$slug_source" || true)"
fi

if ((${#qa_requires[@]} > 0)); then
  tests_mode="$(hook_config_get_str config/gates.json tests_required disabled)"
  for req in "${qa_requires[@]}"; do
    case "${req,,}" in
      gate-tests)
        if [[ "${tests_mode,,}" == "disabled" ]]; then
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
  qa_command=("python3" "scripts/qa-agent.py")
fi

if [[ -n "${CLAUDE_QA_COMMAND:-}" ]]; then
  read -r -a override <<< "${CLAUDE_QA_COMMAND}"
  if ((${#override[@]} > 0)); then
    qa_command=("${override[@]}")
  fi
fi

replace_placeholders() {
  local raw="$1"
  local slug_val="${slug:-unknown}"
  local branch_val="${branch:-detached}"
  raw="${raw//\{slug\}/$slug_val}"
  raw="${raw//\{branch\}/$branch_val}"
  printf '%s\n' "$raw"
}

cmd=()
for part in "${qa_command[@]}"; do
  [[ -z "$part" ]] && continue
  cmd+=("$(replace_placeholders "$part")")
done

if ((${#qa_block[@]} == 0)); then
  qa_block=("blocker" "critical")
fi
if ((${#qa_warn[@]} == 0)); then
  qa_warn=("major" "minor")
fi

block_arg="$(IFS=','; printf '%s' "${qa_block[*]}")"
warn_arg="$(IFS=','; printf '%s' "${qa_warn[*]}")"

runner=("${cmd[@]}" "--gate" "--block-on" "$block_arg" "--warn-on" "$warn_arg")
[[ -n "$slug" ]] && runner+=("--slug" "$slug")
[[ -n "$branch" ]] && runner+=("--branch" "$branch")

report_path="$qa_report"
if [[ -n "$report_path" ]]; then
  report_path="$(replace_placeholders "$report_path")"
  runner+=("--report" "$report_path")
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

echo "[gate-qa] Запуск QA-агента (ветка: $branch, slug: ${slug:-n/a})" >&2
((dry_run == 1)) && echo "[gate-qa] dry-run режим: блокеры не провалят команду." >&2

set +e
"${timeout_cmd[@]}" "${runner[@]}"
status=$?
set -e

if [[ "$status" -eq 127 ]]; then
  echo "[gate-qa] ERROR: не удалось выполнить команду QA (${runner[0]})." >&2
fi

if [[ -n "$report_path" && "$qa_allow_missing" == "0" ]]; then
  if [[ ! -f "$report_path" ]]; then
    echo "[gate-qa] ERROR: отчёт QA не создан: $report_path" >&2
    (( status == 0 )) && status=1
  fi
fi

exit "$status"
