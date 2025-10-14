#!/usr/bin/env bash
set -euo pipefail

# protect-prod.sh
# ----------------
# Hook, который блокирует несанкционированную работу с чувствительными путями.
# Использует секцию protection в .claude/settings.json.
# Переменные окружения:
#   PROTECT_PROD_BYPASS=1  — явный override (или имя из protection.bypassEnv).
#   PROTECT_LOG_ONLY=1     — не блокировать, а только предупреждать.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONFIG_FILE="${ROOT_DIR}/.claude/settings.json"

log() {
  printf '[protect-prod] %s\n' "$*" >&2
}

collect_candidate_files() {
  local -a files=()
  if git rev-parse --verify HEAD >/dev/null 2>&1; then
    while IFS= read -r line; do
      [[ -n "$line" ]] && files+=("$line")
    done < <(git diff --name-only --cached)
    while IFS= read -r line; do
      [[ -n "$line" ]] && files+=("$line")
    done < <(git diff --name-only)
  fi
  while IFS= read -r line; do
    [[ -n "$line" ]] && files+=("$line")
  done < <(git ls-files --others --exclude-standard)

  if ((${#files[@]})); then
    printf '%s\n' "${files[@]}" | sort -u
  fi
}

if [[ ! -f "$CONFIG_FILE" ]]; then
  log "Не найден ${CONFIG_FILE} — пропускаем проверку путей."
  exit 0
fi

readarray -t CHECK_RESULT < <(
  python3 - "$CONFIG_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
data = json.loads(config_path.read_text(encoding="utf-8"))
protection = data.get("protection", {})

bypass_env = protection.get("bypassEnv", "PROTECT_PROD_BYPASS")
log_only_env = protection.get("logOnlyEnv", "PROTECT_LOG_ONLY")
protected = protection.get("protectedGlobs", [])
allowlist = protection.get("allowlist", [])
help_url = protection.get("docs", "docs/customization.md#prod-protection")

print(f"BYPASS_ENV={bypass_env}")
print(f"LOG_ONLY_ENV={log_only_env}")
print("PROTECTED=" + "\0".join(protected))
print("ALLOWLIST=" + "\0".join(allowlist))
print(f"HELP_URL={help_url}")
PY
)

declare BYPASS_ENV=""
declare LOG_ONLY_ENV=""
declare HELP_URL=""

for line in "${CHECK_RESULT[@]}"; do
  case "$line" in
    BYPASS_ENV=*)
      BYPASS_ENV="${line#BYPASS_ENV=}"
      ;;
    LOG_ONLY_ENV=*)
      LOG_ONLY_ENV="${line#LOG_ONLY_ENV=}"
      ;;
    HELP_URL=*)
      HELP_URL="${line#HELP_URL=}"
      ;;
    PROTECTED=*)
      IFS=$'\0' read -r -a _ <<< "${line#PROTECTED=}"
      ;;
    ALLOWLIST=*)
      IFS=$'\0' read -r -a _ <<< "${line#ALLOWLIST=}"
      ;;
  esac
done

if [[ -n "$BYPASS_ENV" && "${!BYPASS_ENV:-0}" == "1" ]]; then
  log "Обнаружен ${BYPASS_ENV}=1 — защита отключена."
  exit 0
fi

mapfile -t CANDIDATE_FILES < <(collect_candidate_files || true)
if ((${#CANDIDATE_FILES[@]} == 0)); then
  exit 0
fi

readarray -t VIOLATIONS < <(
  python3 - "$CONFIG_FILE" "${CANDIDATE_FILES[@]}" <<'PY'
import fnmatch
import json
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
files = sys.argv[2:]
data = json.loads(config_path.read_text(encoding="utf-8"))
protection = data.get("protection", {})

protected = protection.get("protectedGlobs", [])
allowlist = protection.get("allowlist", [])

matches = []

def is_allowed(path):
    return any(fnmatch.fnmatch(path, pattern) for pattern in allowlist)

for path in files:
    if is_allowed(path):
        continue
    for pattern in protected:
        if fnmatch.fnmatch(path, pattern):
            matches.append((path, pattern))
            break

for path, pattern in matches:
    print(f"{path}|{pattern}")
PY
)

if ((${#VIOLATIONS[@]} == 0)); then
  exit 0
fi

log "Обнаружены изменения в защищённых путях:"
for entry in "${VIOLATIONS[@]}"; do
  file="${entry%%|*}"
  pattern="${entry#*|}"
  log "  - ${file} (паттерн: ${pattern})"
done

if [[ -n "$LOG_ONLY_ENV" && "${!LOG_ONLY_ENV:-0}" == "1" ]]; then
  log "${LOG_ONLY_ENV}=1 — только предупреждение (операция не блокирована)."
  exit 0
fi

log "Чтобы добавить исключение, обновите protection.allowlist в .claude/settings.json или переместите файлы."
if [[ -n "$HELP_URL" ]]; then
  log "Подробности: ${HELP_URL}"
fi
exit 1
