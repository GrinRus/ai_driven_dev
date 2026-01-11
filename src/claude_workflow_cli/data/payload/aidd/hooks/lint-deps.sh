#!/usr/bin/env bash
# Предупреждает о зависимостях вне allowlist при изменении Gradle-манифестов (не блокирует)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=hooks/lib.sh
source "${SCRIPT_DIR}/lib.sh"
ROOT_DIR="$(hook_project_root)"
if [[ -z "$ROOT_DIR" ]]; then
  echo "[lint-deps] WARN: aidd root not found; skipping lint." >&2
  exit 0
fi
export ROOT_DIR

if [[ "${CLAUDE_SKIP_STAGE_CHECKS:-0}" != "1" ]]; then
  active_stage="$(hook_resolve_stage "$ROOT_DIR/docs/.active_stage" || true)"
  if [[ "$active_stage" != "implement" ]]; then
    exit 0
  fi
fi

[[ "$(hook_config_get_bool "$ROOT_DIR/config/gates.json" deps_allowlist)" == "1" ]] || exit 0
[[ -f "$ROOT_DIR/config/allowed-deps.txt" ]] || exit 0

allowed=()
while IFS= read -r line; do
  [[ -n "$line" ]] && allowed+=("$line")
done < <(grep -Ev '^\s*(#|$)' "$ROOT_DIR/config/allowed-deps.txt" | sed 's/[[:space:]]//g')
is_allowed() { local ga="$1"; for a in "${allowed[@]}"; do [[ "$ga" == "$a" ]] && return 0; done; return 1; }

# Смотрим добавленные строки в Gradle-манифестах
added=()
if git -C "$ROOT_DIR" rev-parse --verify HEAD >/dev/null 2>&1; then
  while IFS= read -r line; do
    [[ -n "$line" ]] && added+=("$line")
  done < <(git -C "$ROOT_DIR" diff --unified=0 --no-color HEAD -- '**/build.gradle*' 'gradle/libs.versions.toml' | grep '^\+' || true)
fi

for line in "${added[@]}"; do
  ga=""
  if [[ "$line" =~ (implementation|api|compileOnly|runtimeOnly)\([\"\']([^:\"\'\)]+:[^:\"\'\)]+) ]]; then
    ga="${BASH_REMATCH[2]}"
  fi
  [[ -z "$ga" ]] && continue
  if ! is_allowed "$ga"; then
    echo "WARN: dependency '$ga' не в allowlist (config/allowed-deps.txt)" 1>&2
  fi
done

exit 0
